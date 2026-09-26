"""Bound a subprocess and clean up its tree before releasing the log."""
import os
import signal
import subprocess
import time


def stop_tree(process):
    if os.name == 'nt':
        # wait(timeout) has NOT killed the launcher: its descendants are still
        # discoverable by taskkill /T. subprocess.run(timeout) kills it too soon.
        killed = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                capture_output=True, timeout=15,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if killed.returncode and process.poll() is None:
            raise RuntimeError('process tree cleanup failed: '+killed.stderr.decode(errors='replace'))
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=15)


def run_command(command, log, timeout):
    start = time.perf_counter()
    with log.open('w', encoding='utf-8') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
            **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}))
        try:
            code = process.wait(timeout=timeout)
            status = 'success' if code == 0 else 'failed'
        except subprocess.TimeoutExpired:
            stop_tree(process)
            code, status = None, 'timeout'
        except BaseException:
            stop_tree(process)
            raise
    return {'status': status, 'returncode': code, 'seconds': time.perf_counter()-start,
            'pid': process.pid, 'command': command}
