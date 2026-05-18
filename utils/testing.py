"""Testing utilities"""
from agents.base import call_agent

def test_agent(agent_name: str):
    """Test an agent with a simple prompt"""
    print(f"\n🧪 Testing {agent_name}...")
    
    test_prompts = {
        "orchestrator": "We need to build a simple hello world app. What should we do first?",
        "developer": "Write a hello world function in Python",
        "reviewer": "Review this code: def hello(): print('Hello')",
        "researcher": "What's the best way to structure a Flask app?",
        "jr_reviewer": "Review this file:\n```python test.py\ndef add(a, b):\n    return a + b\n```",
        "jr_researcher": "Analyze this file:\n```python test.py\nimport os\nprint('hello')\n```",
        "tech_writer": "Document this file:\n```python test.py\ndef process_data(data):\n    return data\n```"
    }
    
    prompt = test_prompts.get(agent_name, "Hello, can you hear me?")
    
    response = call_agent(agent_name, prompt, "test_task")
    
    if response:
        print(f"\n✅ {agent_name} responded:")
        print("-" * 60)
        print(response[:500])
        print("\n" + "-" * 60)
    else:
        print(f"\n❌ {agent_name} failed to respond")

def test_all_agents():
    """Test all agents"""
    agents = ["orchestrator", "developer", "reviewer", "researcher", 
              "jr_reviewer", "jr_researcher", "tech_writer"]
    
    print(f"\n{'='*60}")
    print(f"🧪 Testing All Agents")
    print(f"{'='*60}")
    
    for agent in agents:
        test_agent(agent)
        print()