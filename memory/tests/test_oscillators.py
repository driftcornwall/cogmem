#!/usr/bin/env python3
"""Unit tests for CognitiveOscillator — damped harmonic oscillator per cognitive dimension."""

import math
import sys
from pathlib import Path

# Allow importing from memory/ without package install
sys.path.insert(0, str(Path(__file__).parent.parent))

from cognitive_state import CognitiveOscillator, OscillatorNetwork, OSCILLATOR_CONFIGS


def test_oscillator_init():
    """Verify defaults: phase=0, amplitude=0, velocity=0."""
    osc = CognitiveOscillator("curiosity", natural_freq=1.0, damping=0.5, baseline=0.5)
    assert osc.name == "curiosity"
    assert osc.phase == 0.0
    assert osc.amplitude == 0.0
    assert osc.velocity == 0.0
    assert osc.natural_freq == 1.0
    assert osc.damping == 0.5
    assert osc.baseline == 0.5


def test_oscillator_impulse():
    """Impulse increases velocity; stepping changes amplitude."""
    osc = CognitiveOscillator("focus", natural_freq=1.0, damping=0.5, baseline=0.5)
    osc.impulse(0.3)
    # Pending force accumulated but not yet applied
    assert osc.velocity == 0.0
    assert osc.amplitude == 0.0

    osc.step(dt=1.0, coupling_force=0.0)
    # After step, the impulse should have moved the oscillator
    assert osc.velocity != 0.0 or osc.amplitude != 0.0


def test_oscillator_spring_return():
    """Displaced oscillator returns toward baseline over 50 steps."""
    osc = CognitiveOscillator("arousal", natural_freq=1.0, damping=0.8, baseline=0.5)
    # Displace via impulse
    osc.impulse(0.5)
    osc.step(dt=1.0, coupling_force=0.0)
    initial_displacement = abs(osc.amplitude - osc.baseline)
    assert initial_displacement > 0.0

    # Run 50 steps — spring should pull back toward baseline
    for _ in range(50):
        osc.step(dt=1.0, coupling_force=0.0)

    final_displacement = abs(osc.amplitude - osc.baseline)
    assert final_displacement < initial_displacement, (
        f"Expected return toward baseline: initial={initial_displacement:.4f}, final={final_displacement:.4f}"
    )


def test_oscillator_underdamped_overshoot():
    """Low damping (0.2) causes overshoot past baseline."""
    osc = CognitiveOscillator("confidence", natural_freq=1.5, damping=0.2, baseline=0.5)
    # Strong positive impulse
    osc.impulse(0.8)
    osc.step(dt=1.0, coupling_force=0.0)

    # Track whether amplitude ever crosses baseline from above to below
    crossed_below = False
    prev_amplitude = osc.amplitude
    for _ in range(100):
        osc.step(dt=1.0, coupling_force=0.0)
        if prev_amplitude >= osc.baseline and osc.amplitude < osc.baseline:
            crossed_below = True
            break
        prev_amplitude = osc.amplitude

    assert crossed_below, "Underdamped oscillator should overshoot past baseline"


def test_oscillator_phase_advances():
    """Phase increments by natural_freq * dt per step."""
    freq = 0.7
    dt = 1.0
    osc = CognitiveOscillator("satisfaction", natural_freq=freq, damping=0.5, baseline=0.5)
    assert osc.phase == 0.0

    osc.step(dt=dt, coupling_force=0.0)
    expected_phase = freq * dt
    assert abs(osc.phase - expected_phase) < 1e-9, f"Expected phase={expected_phase}, got {osc.phase}"

    osc.step(dt=dt, coupling_force=0.0)
    expected_phase = (2 * freq * dt) % (2 * math.pi)
    assert abs(osc.phase - expected_phase) < 1e-9


def test_oscillator_to_dict():
    """Serialization includes all fields."""
    osc = CognitiveOscillator("curiosity", natural_freq=1.2, damping=0.4, baseline=0.6)
    osc.impulse(0.3)
    osc.step(dt=1.0, coupling_force=0.0)

    d = osc.to_dict()
    assert d["name"] == "curiosity"
    assert d["natural_freq"] == 1.2
    assert d["damping"] == 0.4
    assert d["baseline"] == 0.6
    assert "phase" in d
    assert "amplitude" in d
    assert "velocity" in d


def test_oscillator_from_dict():
    """Round-trip through dict preserves state."""
    osc = CognitiveOscillator("arousal", natural_freq=0.9, damping=0.6, baseline=0.45)
    osc.impulse(0.5)
    osc.step(dt=1.0, coupling_force=0.0)
    osc.step(dt=1.0, coupling_force=0.1)

    d = osc.to_dict()
    restored = CognitiveOscillator.from_dict(d)

    assert restored.name == osc.name
    assert restored.natural_freq == osc.natural_freq
    assert restored.damping == osc.damping
    assert restored.baseline == osc.baseline
    assert abs(restored.phase - osc.phase) < 1e-12
    assert abs(restored.amplitude - osc.amplitude) < 1e-12
    assert abs(restored.velocity - osc.velocity) < 1e-12


# ---------------------------------------------------------------------------
# OscillatorNetwork tests (Task 2)
# ---------------------------------------------------------------------------

def test_network_init():
    """5 oscillators with distinct natural frequencies from OSCILLATOR_CONFIGS."""
    net = OscillatorNetwork(coupling_strength=0.3)
    assert len(net.oscillators) == 5

    # Each oscillator should have the frequency from OSCILLATOR_CONFIGS
    freqs = set()
    for name, osc in net.oscillators.items():
        assert osc.name == name
        assert osc.natural_freq == OSCILLATOR_CONFIGS[name]['natural_freq']
        freqs.add(osc.natural_freq)

    # All 5 frequencies are distinct
    assert len(freqs) == 5, f"Expected 5 distinct frequencies, got {len(freqs)}"


def test_network_order_parameter():
    """R=1 when all phases equal; R < 0.5 when evenly spread."""
    net = OscillatorNetwork()

    # All phases start at 0 -> R should be 1.0
    R_sync = net.order_parameter()
    assert abs(R_sync - 1.0) < 1e-9, f"Expected R=1.0 when all phases=0, got {R_sync}"

    # Spread phases evenly around the circle
    names = list(net.oscillators.keys())
    for i, name in enumerate(names):
        net.oscillators[name].phase = (2 * math.pi * i) / len(names)

    R_spread = net.order_parameter()
    assert R_spread < 0.5, f"Expected R < 0.5 when evenly spread, got {R_spread}"


def test_network_coupling_pulls_phases():
    """Same freq but different phases: coupling should increase R over 100 steps."""
    net = OscillatorNetwork(coupling_strength=0.5)

    # Set all to same frequency but spread phases
    names = list(net.oscillators.keys())
    for i, name in enumerate(names):
        net.oscillators[name].natural_freq = 0.5
        net.oscillators[name].phase = (2 * math.pi * i) / len(names)

    R_before = net.order_parameter()

    for _ in range(100):
        net.step(dt=0.1)

    R_after = net.order_parameter()
    assert R_after > R_before, (
        f"Coupling should increase R: before={R_before:.4f}, after={R_after:.4f}"
    )


def test_network_event_impulse():
    """Apply search_success deltas; confidence oscillator should move."""
    net = OscillatorNetwork()

    # search_success deltas from EVENT_DELTAS
    deltas = {
        'curiosity': -0.05,
        'confidence': +0.10,
        'focus': +0.05,
        'arousal': +0.02,
        'satisfaction': +0.05,
    }

    conf_before = net.get_oscillator('confidence').amplitude
    net.apply_event(deltas)
    net.step(dt=1.0)
    conf_after = net.get_oscillator('confidence').amplitude

    assert conf_after != conf_before, (
        f"Confidence should have moved after event impulse: before={conf_before}, after={conf_after}"
    )


def test_network_phase_state_detection():
    """Force all phases same -> state should have synchronization > 0.8."""
    net = OscillatorNetwork()

    # All phases at 0 -> R = 1.0 -> high synchronization
    # Also need high sat_conf coherence for flow/mastery
    for name in net.oscillators:
        net.oscillators[name].phase = 0.0

    state = net.detect_phase_state()
    assert state['synchronization'] > 0.8, (
        f"Expected synchronization > 0.8 when all phases equal, got {state['synchronization']}"
    )
    assert state['state'] in ('flow', 'mastery'), (
        f"Expected flow or mastery with R=1.0 and coherent phases, got {state['state']}"
    )


def test_network_serialize():
    """Round-trip through to_dict/from_dict preserves state."""
    net = OscillatorNetwork(coupling_strength=0.42)

    # Evolve the network so state is non-trivial
    net.apply_event({'curiosity': 0.3, 'arousal': -0.2, 'confidence': 0.1})
    for _ in range(10):
        net.step(dt=1.0)

    d = net.to_dict()
    restored = OscillatorNetwork.from_dict(d)

    assert restored.coupling_strength == net.coupling_strength
    for name in net.oscillators:
        orig = net.oscillators[name]
        rest = restored.oscillators[name]
        assert rest.name == orig.name
        assert abs(rest.phase - orig.phase) < 1e-12
        assert abs(rest.amplitude - orig.amplitude) < 1e-12
        assert abs(rest.velocity - orig.velocity) < 1e-12
        assert rest.natural_freq == orig.natural_freq
        assert rest.damping == orig.damping
        assert rest.baseline == orig.baseline


# ---------------------------------------------------------------------------
# Integration tests — Task 3: Wire into process_event() + DB persistence
# ---------------------------------------------------------------------------

def test_process_event_drives_oscillators(monkeypatch):
    """process_event() should step the oscillator network alongside Beta updates."""
    from cognitive_state import process_event, KV_OSCILLATOR_STATE
    from unittest.mock import MagicMock

    # Mock DB
    mock_db = MagicMock()
    mock_db.kv_get.return_value = None  # Fresh state
    monkeypatch.setattr('cognitive_state.get_db', lambda: mock_db)

    # Clear cached state so get_state() loads from mock DB
    import cognitive_state
    monkeypatch.setattr(cognitive_state, '_current_state', None)

    # Fire event
    result = process_event('search_success')

    # Check oscillator state was saved
    calls = [c for c in mock_db.kv_set.call_args_list
             if c[0][0] == KV_OSCILLATOR_STATE]
    assert len(calls) >= 1, "Oscillator state should be persisted"

    saved = calls[-1][0][1]
    assert 'oscillators' in saved
    assert len(saved['oscillators']) == 5


def test_oscillator_state_persists_across_calls(monkeypatch):
    """Oscillator state should be loaded from DB on subsequent calls."""
    from cognitive_state import OscillatorNetwork, KV_OSCILLATOR_STATE, _load_oscillator_network
    from unittest.mock import MagicMock

    # Create network with some state
    net = OscillatorNetwork()
    net.apply_event({'curiosity': 0.1})
    net.step()
    saved_state = net.to_dict()

    mock_db = MagicMock()
    mock_db.kv_get.side_effect = lambda key: saved_state if key == KV_OSCILLATOR_STATE else None
    monkeypatch.setattr('cognitive_state.get_db', lambda: mock_db)

    net2 = _load_oscillator_network(mock_db)
    # Verify state was restored (phases should match)
    for name in net.oscillators:
        orig = net.oscillators[name]
        restored = net2.oscillators[name]
        assert abs(restored.phase - orig.phase) < 1e-4, (
            f"Phase mismatch for {name}: {restored.phase} vs {orig.phase}"
        )
        assert abs(restored.amplitude - orig.amplitude) < 1e-4, (
            f"Amplitude mismatch for {name}: {restored.amplitude} vs {orig.amplitude}"
        )


# ---------------------------------------------------------------------------
# Task 5: get_oscillator_summary() for priming
# ---------------------------------------------------------------------------

def test_oscillator_summary(monkeypatch):
    """get_oscillator_summary should return compact phase state for priming."""
    from cognitive_state import get_oscillator_summary, KV_OSCILLATOR_STATE, OscillatorNetwork
    from unittest.mock import MagicMock

    net = OscillatorNetwork()
    net.apply_event({'curiosity': 0.1, 'confidence': -0.05})
    net.step()
    net.step()

    mock_db = MagicMock()
    mock_db.kv_get.side_effect = lambda key: net.to_dict() if key == KV_OSCILLATOR_STATE else None
    monkeypatch.setattr('cognitive_state.get_db', lambda: mock_db)

    summary = get_oscillator_summary()
    assert 'phase_state' in summary
    assert 'order_parameter' in summary
    assert summary['phase_state'] in ('flow', 'mastery', 'exploration', 'fatigue', 'processing')
    assert 'dimensions' in summary
    assert 'curiosity' in summary['dimensions']


# ---------------------------------------------------------------------------
# Task 6: Integration tests — full session simulation
# ---------------------------------------------------------------------------

def test_full_session_simulation():
    """Simulate a realistic session: events should drive oscillator dynamics."""
    from cognitive_state import OscillatorNetwork

    net = OscillatorNetwork(coupling_strength=0.3)
    events = [
        {'curiosity': +0.10, 'confidence': -0.05, 'focus': -0.15,
         'arousal': +0.05, 'satisfaction': 0},
        {'curiosity': -0.05, 'confidence': +0.10, 'focus': +0.05,
         'arousal': +0.02, 'satisfaction': +0.05},
        {'curiosity': -0.05, 'confidence': +0.10, 'focus': +0.05,
         'arousal': +0.02, 'satisfaction': +0.05},
        {'curiosity': +0.15, 'confidence': -0.10, 'focus': -0.05,
         'arousal': +0.05, 'satisfaction': -0.05},
        {'curiosity': -0.02, 'confidence': +0.05, 'focus': +0.02,
         'arousal': +0.03, 'satisfaction': +0.08},
        {'curiosity': -0.05, 'confidence': +0.05, 'focus': +0.15,
         'arousal': -0.02, 'satisfaction': +0.03},
    ]

    R_values = []
    states = []
    for event_deltas in events:
        net.apply_event(event_deltas)
        net.step()
        R_values.append(net.order_parameter())
        states.append(net.detect_phase_state()['state'])

    assert net.step_count == 6
    assert any(R != R_values[0] for R in R_values), "Order parameter should change"
    for osc in net.oscillators.values():
        assert osc.phase > 0, f"{osc.name} phase should have advanced"
    valid_states = {'flow', 'exploration', 'fatigue', 'mastery', 'processing'}
    for s in states:
        assert s in valid_states


def test_long_session_stability():
    """Oscillator network should remain stable over many events."""
    from cognitive_state import OscillatorNetwork
    import random
    random.seed(42)

    net = OscillatorNetwork(coupling_strength=0.3)
    for _ in range(200):
        deltas = {dim: random.uniform(-0.15, 0.15) for dim in
                  ['curiosity', 'confidence', 'focus', 'arousal', 'satisfaction']}
        net.apply_event(deltas)
        net.step()

    for osc in net.oscillators.values():
        assert 0.0 <= osc.amplitude <= 1.0, \
            f"{osc.name} amplitude out of bounds: {osc.amplitude}"
    R = net.order_parameter()
    assert 0.0 <= R <= 1.0
    d = net.to_dict()
    net2 = OscillatorNetwork.from_dict(d)
    assert len(net2.oscillators) == 5


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
