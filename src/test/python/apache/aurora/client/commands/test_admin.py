#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import contextlib

from mock import Mock, patch

from apache.aurora.client.api import AuroraClientAPI
from apache.aurora.client.commands.admin import get_locks, increase_quota, query, set_quota
from apache.aurora.client.commands.util import AuroraClientCommandTest

from gen.apache.aurora.api.constants import ACTIVE_STATES, TERMINAL_STATES
from gen.apache.aurora.api.ttypes import (
    AssignedTask,
    GetLocksResult,
    GetQuotaResult,
    Identity,
    JobKey,
    Lock,
    LockKey,
    ResourceAggregate,
    Response,
    ResponseCode,
    Result,
    ScheduledTask,
    ScheduleStatus,
    ScheduleStatusResult,
    TaskConfig,
    TaskQuery
)


class TestQueryCommand(AuroraClientCommandTest):

  @classmethod
  def setup_mock_options(cls, force=False, shards=None, states='RUNNING', listformat=None):
    mock_options = Mock(spec=['force', 'shards', 'states', 'listformat', 'verbosity'])
    mock_options.force = force
    mock_options.shards = shards
    mock_options.states = states
    mock_options.listformat = listformat or '%role%/%jobName%/%instanceId% %status%'
    mock_options.verbosity = False
    return mock_options

  @classmethod
  def create_response(cls, tasks, response_code=None):
    response_code = ResponseCode.OK if response_code is None else response_code
    resp = Response(responseCode=response_code, messageDEPRECATED='test')
    resp.result = Result(scheduleStatusResult=ScheduleStatusResult(tasks=tasks))
    return resp

  @classmethod
  def create_task(cls):
    return [ScheduledTask(
        assignedTask=AssignedTask(
            instanceId=0,
            task=TaskConfig(owner=Identity(role='test_role'), jobName='test_job')),
        status=ScheduleStatus.RUNNING
    )]

  @classmethod
  def task_query(cls):
    return TaskQuery(
        owner=Identity(role=None),
        environment=None,
        jobName=None,
        instanceIds=set(),
        statuses=set([ScheduleStatus.RUNNING]))

  def test_query(self):
    """Tests successful execution of the query command."""
    mock_options = self.setup_mock_options(force=True)
    mock_api, mock_scheduler_proxy = self.create_mock_api()
    with contextlib.nested(
        patch('twitter.common.app.get_options', return_value=mock_options),
        patch('apache.aurora.client.api.SchedulerProxy', return_value=mock_scheduler_proxy),
        patch('apache.aurora.client.commands.admin.CLUSTERS', new=self.TEST_CLUSTERS)):

      mock_scheduler_proxy.getTasksStatus.return_value = self.create_response(self.create_task())

      query([self.TEST_CLUSTER], mock_options)

      mock_scheduler_proxy.getTasksStatus.assert_called_with(self.task_query())

  def test_query_fails(self):
    """Tests failed execution of the query command."""
    mock_options = self.setup_mock_options()
    mock_api, mock_scheduler_proxy = self.create_mock_api()
    with contextlib.nested(
        patch('twitter.common.app.get_options', return_value=mock_options),
        patch('apache.aurora.client.api.SchedulerProxy', return_value=mock_scheduler_proxy),
        patch('apache.aurora.client.commands.admin.CLUSTERS', new=self.TEST_CLUSTERS)):

      mock_scheduler_proxy.getTasksStatus.return_value = self.create_response(self.create_task())

      try:
        query([self.TEST_CLUSTER], mock_options)
      except SystemExit:
        pass
      else:
        assert 'Expected exception is not raised'


class TestIncreaseQuotaCommand(AuroraClientCommandTest):

  @classmethod
  def setup_mock_options(cls):
    mock_options = Mock(spec=['verbosity'])
    mock_options.verbosity = 'verbose'
    return mock_options

  @classmethod
  def create_response(cls, quota, prod, non_prod, response_code=None):
    response_code = ResponseCode.OK if response_code is None else response_code
    resp = Response(responseCode=response_code, messageDEPRECATED='test')
    resp.result = Result(getQuotaResult=GetQuotaResult(
        quota=quota, prodConsumption=prod, nonProdConsumption=non_prod))
    return resp

  def test_increase_quota(self):
    """Tests successful execution of the increase_quota command."""
    mock_options = self.setup_mock_options()
    with contextlib.nested(
        patch('twitter.common.app.get_options', return_value=mock_options),
        patch('apache.aurora.client.commands.admin.AuroraClientAPI',
            new=Mock(spec=AuroraClientAPI)),
        patch('apache.aurora.client.commands.admin.CLUSTERS', new=self.TEST_CLUSTERS)
    ) as (_, api, _):

      role = 'test_role'
      api.return_value.get_quota.return_value = self.create_response(
          ResourceAggregate(20.0, 4000, 6000),
          ResourceAggregate(15.0, 2000, 3000),
          ResourceAggregate(6.0, 200, 600),
      )
      api.return_value.set_quota.return_value = self.create_simple_success_response()

      increase_quota([self.TEST_CLUSTER, role, '4.0', '1MB', '1MB'])

      api.return_value.set_quota.assert_called_with(role, 24.0, 4001, 6001)
      assert type(api.return_value.set_quota.call_args[0][1]) == type(float())
      assert type(api.return_value.set_quota.call_args[0][2]) == type(int())
      assert type(api.return_value.set_quota.call_args[0][3]) == type(int())


class TestSetQuotaCommand(AuroraClientCommandTest):

  @classmethod
  def setup_mock_options(cls):
    mock_options = Mock(spec=['verbosity'])
    mock_options.verbosity = 'verbose'
    return mock_options

  @classmethod
  def create_response(cls, quota, prod, non_prod, response_code=None):
    response_code = ResponseCode.OK if response_code is None else response_code
    resp = Response(responseCode=response_code, messageDEPRECATED='test')
    resp.result = Result(getQuotaResult=GetQuotaResult(
      quota=quota, prodConsumption=prod, nonProdConsumption=non_prod))
    return resp

  def test_set_quota(self):
    """Tests successful execution of the set_quota command."""
    mock_options = self.setup_mock_options()
    with contextlib.nested(
        patch('twitter.common.app.get_options', return_value=mock_options),
        patch('apache.aurora.client.commands.admin.AuroraClientAPI',
              new=Mock(spec=AuroraClientAPI)),
        patch('apache.aurora.client.commands.admin.CLUSTERS', new=self.TEST_CLUSTERS)
    ) as (_, api, _):

      role = 'test_role'
      api.return_value.set_quota.return_value = self.create_simple_success_response()

      set_quota([self.TEST_CLUSTER, role, '4.0', '10MB', '10MB'])

      api.return_value.set_quota.assert_called_with(role, 4.0, 10, 10)
      assert type(api.return_value.set_quota.call_args[0][1]) == type(float())
      assert type(api.return_value.set_quota.call_args[0][2]) == type(int())
      assert type(api.return_value.set_quota.call_args[0][3]) == type(int())


class TestGetLocksCommand(AuroraClientCommandTest):

  MESSAGE = 'test message'
  USER = 'test user'
  LOCKS = [Lock(
    key=LockKey(job=JobKey('role', 'env', 'name')),
    token='test token',
    user=USER,
    timestampMs='300',
    message=MESSAGE)]

  @classmethod
  def setup_mock_options(cls):
    mock_options = Mock(spec=['verbosity'])
    mock_options.verbosity = 'verbose'
    return mock_options

  @classmethod
  def create_response(cls, locks, response_code=None):
    response_code = ResponseCode.OK if response_code is None else response_code
    resp = Response(responseCode=response_code, messageDEPRECATED='test')
    resp.result = Result(getLocksResult=GetLocksResult(locks=locks))
    return resp

  def test_get_locks(self):
    """Tests successful execution of the get_locks command."""
    mock_options = self.setup_mock_options()
    with contextlib.nested(
        patch('twitter.common.app.get_options', return_value=mock_options),
        patch('apache.aurora.client.commands.admin.AuroraClientAPI',
              new=Mock(spec=AuroraClientAPI)),
        patch('apache.aurora.client.commands.admin.CLUSTERS', new=self.TEST_CLUSTERS),
        patch('apache.aurora.client.commands.admin.print_results'),
    ) as (_, api, _, mock_print_results):

      api.return_value.get_locks.return_value = self.create_response(self.LOCKS)

      get_locks([self.TEST_CLUSTER])

      assert api.return_value.get_locks.call_count == 1
      assert mock_print_results.call_count == 1
      assert "'message': '%s'" % self.MESSAGE in mock_print_results.call_args[0][0][0]
      assert "'user': '%s'" % self.USER in mock_print_results.call_args[0][0][0]
