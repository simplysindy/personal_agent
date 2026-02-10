#!/usr/bin/env python3
"""Test script for the agent."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.agent import AgentGraph


def main():
    """Test the agent with sample queries."""
    print("=" * 60)
    print("Personal Agent - Test Script")
    print("=" * 60)

    print("\nInitializing agent...")
    agent = AgentGraph()
    agent.initialize()

    test_queries = [
        "What projects am I working on?",
        "What do I know about Docker?",
        "Tell me about the ACE program",
    ]

    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print("-" * 60)

        try:
            result = agent.invoke(query)
            print(f"\nIntent: {result.get('intent', 'unknown')}")
            print(f"\nResponse:\n{result.get('response', 'No response')[:500]}")

            if result.get('context'):
                print(f"\nSources: {len(result['context'])} items retrieved")

        except Exception as e:
            print(f"Error: {e}")

    # Interactive mode
    print("\n" + "=" * 60)
    print("Interactive mode (type 'quit' to exit)")
    print("=" * 60)

    while True:
        try:
            query = input("\nYou: ").strip()
            if query.lower() in ('quit', 'exit', 'q'):
                break
            if not query:
                continue

            result = agent.invoke(query)
            print(f"\nAgent: {result.get('response', 'No response')}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

    agent.close()
    print("\nGoodbye!")


if __name__ == "__main__":
    main()
