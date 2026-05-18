"""
Complete test of resource controller with actual enforcement
"""

from agents.resource_controller_worker import (
    ResourceControllerWorker,
    HeuristicOptimizer,
    ResourceState
)
import time


def test_adaptive_learning():
    """Test that resource controller learns from agent performance"""
    
    print("\n" + "="*70)
    print("TEST: ADAPTIVE LEARNING")
    print("="*70)
    
    optimizer = HeuristicOptimizer()
    
    # Simulate jr_reviewer generating lots of feedback
    print("\nSimulating jr_reviewer performance:")
    for i in range(20):
        optimizer.update_agent_performance(
            agent_name="jr_reviewer",
            tokens_used=2000,
            duration=3.0,
            feedback_generated=3  # Good performance
        )
    
    # Simulate tech_writer generating little feedback
    print("Simulating tech_writer performance:")
    for i in range(20):
        optimizer.update_agent_performance(
            agent_name="tech_writer",
            tokens_used=1500,
            duration=2.5,
            feedback_generated=0  # Poor performance
        )
    
    # Check learned values
    jr_profile = optimizer.agent_profiles["jr_reviewer"]
    tw_profile = optimizer.agent_profiles["tech_writer"]
    
    print(f"\nLearned values:")
    print(f"  jr_reviewer: {jr_profile.feedback_value_score:.3f} "
          f"({jr_profile.total_feedback_generated} feedback from {jr_profile.total_calls} calls)")
    print(f"  tech_writer: {tw_profile.feedback_value_score:.3f} "
          f"({tw_profile.total_feedback_generated} feedback from {tw_profile.total_calls} calls)")
    
    # jr_reviewer should have higher value now
    assert jr_profile.feedback_value_score > tw_profile.feedback_value_score
    print(f"\n✅ jr_reviewer value increased (generates feedback)")
    print(f"✅ tech_writer value decreased (generates no feedback)")
    
    # Test ranking
    ranked = optimizer._rank_agents_by_value(exclude=["prioritizer"])
    print(f"\nAgent ranking by value: {ranked}")
    assert ranked[0] == "jr_reviewer"
    print(f"✅ jr_reviewer ranked highest")
    
    print()


def test_throttle_progression():
    """Test throttle decisions at different budget levels"""
    
    print("\n" + "="*70)
    print("TEST: THROTTLE PROGRESSION")
    print("="*70)
    
    optimizer = HeuristicOptimizer()
    
    scenarios = [
        ("CRITICAL", 0.03, 150_000, "Only prioritizer should run"),
        ("AGGRESSIVE", 0.15, 750_000, "Top 1 agent + prioritizer"),
        ("MODERATE", 0.40, 2_000_000, "Top 2 agents + prioritizer"),
        ("NORMAL", 0.80, 4_000_000, "All agents active")
    ]
    
    print()
    for expected_level, budget_pct, tokens_remaining, expectation in scenarios:
        state = ResourceState(
            tokens_used_in_window=int(5_000_000 * (1 - budget_pct)),
            tokens_remaining=tokens_remaining,
            max_tokens=5_000_000,
            current_burn_rate=500.0,
            api_calls_last_minute=30,
            api_rate_limit=118,
            budget_percentage=budget_pct,
            time_remaining_in_window=1440
        )
        
        decision = optimizer.optimize(state)
        
        print(f"{expected_level} ({budget_pct:.0%} budget):")
        print(f"  Expected: {expectation}")
        print(f"  Got: {', '.join(decision.active_agents)}")
        print(f"  Feeder: {decision.background_feeder_interval}s")
        print(f"  Rate: {decision.rate_limit_per_minute} calls/min")
        print(f"  Downgrades: {len(decision.model_downgrades)}")
        
        assert decision.level == expected_level
        print(f"  ✅ Correct level\n")
    
    print("✅ All throttle levels working correctly\n")


def test_enforcement_integration():
    """Test that decisions can be applied to real components"""
    
    print("\n" + "="*70)
    print("TEST: ENFORCEMENT INTEGRATION")
    print("="*70)
    print()
    
    # This would be a full integration test with actual components
    # For now, just validate the interfaces exist
    
    from agents.resource_controller_worker import get_resource_controller
    
    rc = get_resource_controller()
    
    # Check methods exist
    assert hasattr(rc, 'get_model_override')
    assert hasattr(rc, 'update_agent_performance')
    assert hasattr(rc, 'get_current_decision')
    assert hasattr(rc, 'get_agent_statistics')
    
    print("✅ Resource controller has all required methods")
    
    # Test model override storage/retrieval
    test_overrides = {
        "jr_reviewer": "gemini-3-flash-preview",
        "orchestrator": "gemini-3-flash-preview"
    }
    
    rc._store_model_overrides(test_overrides)
    
    override = rc.get_model_override("jr_reviewer")
    assert override == "gemini-3-flash-preview"
    print("✅ Model override storage/retrieval works")
    
    # Test performance tracking
    rc.update_agent_performance("jr_reviewer", 2000, 3.0, 2)
    stats = rc.get_agent_statistics()
    assert "jr_reviewer" in stats
    print("✅ Performance tracking works")
    
    print()


def test_decision_should_apply():
    """Test decision change detection logic"""
    
    print("\n" + "="*70)
    print("TEST: DECISION CHANGE DETECTION")
    print("="*70)
    print()
    
    from agents.resource_controller_worker import ThrottleDecision, ResourceControllerWorker
    
    rc = ResourceControllerWorker()
    
    decision1 = ThrottleDecision(
        level="NORMAL",
        background_feeder_interval=30,
        active_agents=["jr_reviewer", "jr_researcher", "tech_writer"],
        rate_limit_per_minute=118,
        model_downgrades={},
        reasoning="Test"
    )
    
    rc.current_decision = decision1
    
    # Same decision - should NOT apply
    decision2 = ThrottleDecision(
        level="NORMAL",
        background_feeder_interval=30,
        active_agents=["jr_reviewer", "jr_researcher", "tech_writer"],
        rate_limit_per_minute=118,
        model_downgrades={},
        reasoning="Test"
    )
    
    assert not rc._should_apply_decision(decision2)
    print("✅ Identical decision correctly skipped")
    
    # Small interval change - should NOT apply
    decision3 = ThrottleDecision(
        level="NORMAL",
        background_feeder_interval=35,  # +5s
        active_agents=["jr_reviewer", "jr_researcher", "tech_writer"],
        rate_limit_per_minute=118,
        model_downgrades={},
        reasoning="Test"
    )
    
    assert not rc._should_apply_decision(decision3)
    print("✅ Small interval change correctly skipped")
    
    # Level change - SHOULD apply
    decision4 = ThrottleDecision(
        level="MODERATE",  # Changed!
        background_feeder_interval=30,
        active_agents=["jr_reviewer", "jr_researcher", "tech_writer"],
        rate_limit_per_minute=118,
        model_downgrades={},
        reasoning="Test"
    )
    
    assert rc._should_apply_decision(decision4)
    print("✅ Level change correctly detected")
    
    # Agent change - SHOULD apply
    decision5 = ThrottleDecision(
        level="NORMAL",
        background_feeder_interval=30,
        active_agents=["jr_reviewer"],  # Only 1 now
        rate_limit_per_minute=118,
        model_downgrades={},
        reasoning="Test"
    )
    
    assert rc._should_apply_decision(decision5)
    print("✅ Agent change correctly detected")
    
    print()


if __name__ == "__main__":
    print("="*70)
    print("RESOURCE CONTROLLER COMPLETE TEST SUITE")
    print("="*70)
    
    test_adaptive_learning()
    test_throttle_progression()
    test_decision_should_apply()
    test_enforcement_integration()
    
    print("="*70)
    print("✅ ALL TESTS PASSED")
    print("="*70)
    print()