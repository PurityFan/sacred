#!/usr/bin/env python
# coding=utf-8
from __future__ import division, print_function, unicode_literals
from datetime import datetime
import mock
import pytest
from sacred.run import Run
from sacred.config.config_summary import ConfigSummary
from sacred.utils import ObserverError


@pytest.fixture
def run():
    config = {'a': 17, 'foo': {'bar': True, 'baz': False}, 'seed': 1234}
    config_mod = ConfigSummary()
    main_func = mock.Mock(return_value=123)
    logger = mock.Mock()
    observer = [mock.Mock()]
    return Run(config, config_mod, main_func, observer, logger, {}, {}, [], [])


def test_run_attributes(run):
    assert isinstance(run.config, dict)
    assert isinstance(run.config_modifications, ConfigSummary)
    assert isinstance(run.experiment_info, dict)
    assert isinstance(run.host_info, dict)
    assert isinstance(run.info, dict)


def test_run_state_attributes(run):
    assert run.start_time is None
    assert run.stop_time is None
    assert run.captured_out is None
    assert run.result is None


def test_run_run(run):
    assert run() == 123
    assert (run.start_time - datetime.now()).total_seconds() < 1
    assert (run.stop_time - datetime.now()).total_seconds() < 1
    assert run.result == 123
    assert run.captured_out == ''


def test_run_emits_events_if_successful(run):
    run()

    observer = run._observers[0]
    assert observer.started_event.called
    assert observer.heartbeat_event.called
    assert observer.completed_event.called
    assert not observer.interrupted_event.called
    assert not observer.failed_event.called


def test_run_emits_events_if_interrupted(run):
    observer = run._observers[0]
    run.main_function = mock.Mock(side_effect=KeyboardInterrupt)
    with pytest.raises(KeyboardInterrupt):
        run()
    assert observer.started_event.called
    assert observer.heartbeat_event.called
    assert not observer.completed_event.called
    assert observer.interrupted_event.called
    assert not observer.failed_event.called


def test_run_emits_events_if_failed(run):
    observer = run._observers[0]
    run.main_function = mock.Mock(side_effect=TypeError)
    with pytest.raises(TypeError):
        run()
    assert observer.started_event.called
    assert observer.heartbeat_event.called
    assert not observer.completed_event.called
    assert not observer.interrupted_event.called
    assert observer.failed_event.called


def test_run_started_event(run):
    observer = run._observers[0]
    run()
    observer.started_event.assert_called_with(
        ex_info=run.experiment_info,
        host_info=run.host_info,
        start_time=run.start_time,
        config=run.config
    )


def test_run_completed_event(run):
    observer = run._observers[0]
    run()
    observer.completed_event.assert_called_with(
        stop_time=run.stop_time,
        result=run.result
    )


def test_run_heartbeat_event(run):
    observer = run._observers[0]
    run.info['test'] = 321
    run()
    call_args, call_kwargs = observer.heartbeat_event.call_args_list[0]
    assert call_kwargs['info'] == run.info
    assert call_kwargs['captured_out'] == run.captured_out
    assert (call_kwargs['beat_time'] - datetime.now()).total_seconds() < 1


def test_run_artifact_event(run):
    observer = run._observers[0]
    run.add_artifact('/tmp/my_artifact.dat')
    observer.artifact_event.assert_called_with(filename='/tmp/my_artifact.dat')


def test_run_resource_event(run):
    observer = run._observers[0]
    with pytest.raises((OSError, IOError)):
        run.open_resource('/tmp/my_artifact.dat')
    observer.resource_event.assert_called_with(filename='/tmp/my_artifact.dat')


def test_run_cannot_be_started_twice(run):
    run()
    with pytest.raises(RuntimeError):
        run()


def test_run_observer_failure_on_startup_not_caught(run):
    observer = run._observers[0]
    observer.started_event.side_effect = ObserverError
    with pytest.raises(ObserverError):
        run()


def test_run_observer_error_in_heartbeat_is_caught(run):
    observer = run._observers[0]
    observer.heartbeat_event.side_effect = ObserverError
    run()
    assert observer in run._failed_observers
    assert observer.started_event.called
    assert observer.heartbeat_event.called
    assert observer.completed_event.called


def test_run_exception_in_heartbeat_is_not_caught(run):
    observer = run._observers[0]
    observer.heartbeat_event.side_effect = TypeError
    with pytest.raises(TypeError):
        run()
    assert observer in run._failed_observers
    assert observer.started_event.called
    assert observer.heartbeat_event.called
    assert not observer.completed_event.called
    assert not observer.interrupted_event.called
    # assert observer.failed_event.called  # TODO: make this happen


def test_run_exception_in_completed_event_is_caught(run):
    observer = run._observers[0]
    observer2 = mock.Mock()
    run._observers.append(observer2)
    observer.completed_event.side_effect = TypeError
    run()
    assert observer.completed_event.called
    assert observer2.completed_event.called


def test_run_exception_in_interrupted_event_is_caught(run):
    observer = run._observers[0]
    observer2 = mock.Mock()
    run._observers.append(observer2)
    observer.interrupted_event.side_effect = TypeError
    run.main_function = mock.Mock(side_effect=KeyboardInterrupt)
    with pytest.raises(KeyboardInterrupt):
        run()
    assert observer.interrupted_event.called
    assert observer2.interrupted_event.called


def test_run_exception_in_failed_event_is_caught(run):
    observer = run._observers[0]
    observer2 = mock.Mock()
    run._observers.append(observer2)
    observer.failed_event.side_effect = TypeError
    run.main_function = mock.Mock(side_effect=AttributeError)
    with pytest.raises(AttributeError):
        run()
    assert observer.failed_event.called
    assert observer2.failed_event.called
