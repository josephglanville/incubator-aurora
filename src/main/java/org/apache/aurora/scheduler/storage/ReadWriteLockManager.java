/**
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.aurora.scheduler.storage;

import java.util.concurrent.locks.ReentrantReadWriteLock;

import com.google.common.base.Preconditions;

import static java.util.Objects.requireNonNull;

/**
 * A lock manager that wraps a ReadWriteLock and detects ill-fated attempts to upgrade
 * a read-locked thread to a write-locked thread, which would otherwise deadlock.
 */
public class ReadWriteLockManager {
  private final ReentrantReadWriteLock managedLock = new ReentrantReadWriteLock();

  private enum LockMode {
    NONE,
    READ,
    WRITE
  }

  public enum LockType {
    READ(LockMode.READ),
    WRITE(LockMode.WRITE);

    private LockMode mode;

    private LockType(LockMode mode) {
      this.mode = mode;
    }

    LockMode getMode() {
      return mode;
    }
  }

  private static class LockState {
    private LockMode initialLockMode = LockMode.NONE;
    private int lockCount = 0;

    private boolean lockAcquired(LockMode mode) {
      boolean stateChanged = false;
      if (initialLockMode == LockMode.NONE) {
        initialLockMode = mode;
        stateChanged = true;
      }
      if (initialLockMode.equals(mode)) {
        lockCount++;
      }
      return stateChanged;
    }

    private void lockReleased(LockMode mode) {
      if (initialLockMode.equals(mode)) {
        lockCount--;
        if (lockCount == 0) {
          initialLockMode = LockMode.NONE;
        }
      }
    }
  }

  private final ThreadLocal<LockState> lockState = new ThreadLocal<LockState>() {
    @Override
    protected LockState initialValue() {
      return new LockState();
    }
  };

  /**
   * Blocks until this thread has acquired the requested lock.
   *
   * @param type Type of lock to acquire.
   * @return {@code true} if the lock was newly-acquired, or {@code false} if this thread previously
   *         secured the lock and has yet to release it.
   */
  public boolean lock(LockType type) {
    requireNonNull(type);

    if (LockType.READ == type) {
      managedLock.readLock().lock();
    } else {
      Preconditions.checkState(lockState.get().initialLockMode != LockMode.READ,
          "A read operation may not be upgraded to a write operation.");

      managedLock.writeLock().lock();
    }

    return lockState.get().lockAcquired(type.getMode());
  }

  /**
   * Releases this thread's lock of the given type.
   *
   * @param type Type of lock to release.
   */
  public void unlock(LockType type) {
    requireNonNull(type);

    if (LockType.READ == type) {
      managedLock.readLock().unlock();
    } else {
      managedLock.writeLock().unlock();
    }

    lockState.get().lockReleased(type.getMode());
  }

  /**
   * Gets an approximation for the number of threads waiting to acquire the read or write lock.
   *
   * @see ReentrantReadWriteLock#getQueueLength()
   * @return The estimated number of threads waiting for this lock.
   */
  public int getQueueLength() {
    return managedLock.getQueueLength();
  }
}
