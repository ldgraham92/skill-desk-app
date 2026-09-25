"""Cooperative job cancellation and bounded child-process cleanup."""
from contextlib import contextmanager
import os
import signal
import subprocess
import threading
import time

_local=threading.local()


class Cancelled(RuntimeError):
    pass


@contextmanager
def cancellation(event):
    previous=getattr(_local,'event',None)
    _local.event=event
    try: yield
    finally: _local.event=previous


def checkpoint():
    event=getattr(_local,'event',None)
    if event is not None and event.is_set(): raise Cancelled('Job cancelled. No skills were installed.')


def stop_process(process):
    # Each job process owns a group, so grandchildren cannot keep inference or
    # a repository download running after the parent is stopped.
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=8)
    else:
        try: os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError: pass
        try: process.wait(timeout=1)
        except subprocess.TimeoutExpired: pass
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    try: process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill();process.wait(timeout=3)


def run_process(command, **kwargs):
    event=getattr(_local,'event',None)
    if event is None: return subprocess.run(command,**kwargs)
    checkpoint()
    timeout=kwargs.pop('timeout',300)
    content=kwargs.pop('input',None)
    if content is not None: kwargs['stdin']=subprocess.PIPE
    if kwargs.pop('capture_output',False): kwargs.update(stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if os.name=='nt': kwargs['creationflags']=kwargs.get('creationflags',0)|subprocess.CREATE_NEW_PROCESS_GROUP
    else: kwargs['start_new_session']=True
    process=subprocess.Popen(command,**kwargs)
    deadline=time.monotonic()+timeout
    finished=threading.Event()
    result={}
    def communicate():
        try: result['output']=process.communicate(input=content)
        except BaseException as error: result['error']=error
        finally: finished.set()
    # One communicate call owns stdin/stdout. Retrying communicate after short
    # timeouts can strand partially written stdin on Python 3.9.
    reader=threading.Thread(target=communicate,daemon=True)
    reader.start()
    try:
        while not finished.wait(.1):
            checkpoint()
            if time.monotonic()>=deadline: raise subprocess.TimeoutExpired(command,timeout)
        checkpoint()
        if 'error' in result: raise result['error']
        stdout,stderr=result['output']
        return subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
    except BaseException:
        try: stop_process(process)
        finally:
            reader.join(timeout=3)
            for stream in (process.stdin,process.stdout,process.stderr):
                if stream is not None and not stream.closed: stream.close()
        raise
