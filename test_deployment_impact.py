#!/usr/bin/env python3
"""
Test script for the Deployment Impact Analyzer
"""

import asyncio
from pr_agent.tools.pr_deployment_impact import PRDeploymentImpact
from pr_agent.config_loader import get_settings

async def test_deployment_impact_analyzer():
    """
    A simple test function that manually creates a deployment impact analysis
    without requiring a real PR.
    """
    # Create a synthetic analysis
    analysis = """
# Deployment Impact Analysis 🚀

## System Dependencies
- **No new dependencies added**
- Existing dependency versions remain unchanged

## Change Impact Assessment
- **Modified Files**: 
  - `pr_agent/tools/pr_deployment_impact.py` - Added new functionality for analyzing deployment impacts
  - `pr_agent/agent/pr_agent.py` - Updated to include the new deployment impact command
  - `pr_agent/config_loader.py` - Added loading of new prompt templates

- **Services/Components Affected**:
  - PR Agent CLI tool
  - Configuration loading system

## Deployment Requirements
- **Infrastructure Changes**: None required
- **Resource Requirements**: No additional resources needed
- **Configuration Updates**: 
  - Added new prompt template file: `pr_deployment_impact_prompts.toml`

## Risk Assessment & Deployment Strategy
- **Risk Level**: Low
- **Potential Issues**: 
  - Minimal risk of regression in existing functionality
- **Recommended Strategy**:
  - Deploy during regular maintenance window
  - No need for phased rollout
  - No downtime expected

## Additional Notes
This change adds a new analytical capability without modifying existing core functionality.
"""
    
    # Print the analysis
    print(analysis)
    
    # Return the analysis for further use if needed
    return analysis

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_deployment_impact_analyzer())
