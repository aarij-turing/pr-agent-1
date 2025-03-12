import asyncio
import copy
import traceback
from datetime import datetime
from functools import partial
from typing import Dict, List, Optional

from jinja2 import Environment, StrictUndefined

from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.algo.pr_processing import (
    add_ai_metadata_to_diff_files,
    get_pr_diff,
    retry_with_fallback_models
)
from pr_agent.algo.token_handler import TokenHandler
from pr_agent.algo.utils import ModelType, load_yaml
from pr_agent.config_loader import get_settings
from pr_agent.git_providers import get_git_provider_with_context
from pr_agent.git_providers.git_provider import get_main_pr_language
from pr_agent.log import get_logger


class PRDeploymentImpact:
    """
    This agent predicts how code changes might affect production systems by analyzing
    dependencies, changes to services, endpoints, data models, and infrastructure resources.
    """

    def __init__(self, pr_url: str, cli_mode=False, args: list = None, 
                 ai_handler: partial[BaseAiHandler,] = LiteLLMAIHandler):
        """
        Initialize the PRDeploymentImpact agent.
        
        Args:
            pr_url (str): The URL of the pull request to analyze.
            args (list, optional): Additional arguments. Defaults to None.
            ai_handler: The AI handler to use. Defaults to LiteLLMAIHandler.
        """
        self.git_provider = get_git_provider_with_context(pr_url)
        self.main_language = get_main_pr_language(
            self.git_provider.get_languages(), self.git_provider.get_files()
        )

        self.ai_handler = ai_handler()
        self.ai_handler.main_pr_language = self.main_language
        self.patches_diff = None
        self.prediction = None
        self.pr_url = pr_url
        self.cli_mode = cli_mode
        
        self.pr_description, self.pr_description_files = (
            self.git_provider.get_pr_description(split_changes_walkthrough=True))
        
        if (self.pr_description_files and get_settings().get("config.is_auto_command", False) and
                get_settings().get("config.enable_ai_metadata", False)):
            add_ai_metadata_to_diff_files(self.git_provider, self.pr_description_files)
            get_logger().debug(f"AI metadata added to this command")
        else:
            get_settings().set("config.enable_ai_metadata", False)
            get_logger().debug(f"AI metadata is disabled for this command")

        # Set variables to use in the prompt
        self.vars = {
            "title": self.git_provider.pr.title,
            "branch": self.git_provider.get_pr_branch(),
            "description": self.pr_description,
            "language": self.main_language,
            "diff": "",  # empty diff for initial calculation
            "commit_messages_str": self.git_provider.get_commit_messages(),
            "extra_instructions": get_settings().pr_deployment_impact.extra_instructions 
                                 if hasattr(get_settings(), 'pr_deployment_impact') 
                                 and hasattr(get_settings().pr_deployment_impact, 'extra_instructions') 
                                 else "",
            "is_ai_metadata": get_settings().get("config.enable_ai_metadata", False),
            "date": datetime.now().strftime('%Y-%m-%d'),
        }

        # Default system and user prompts if not defined in settings
        default_system_prompt = """
        You are a deployment impact analyzer. Your task is to analyze code changes in a pull request and predict 
        how they might affect production systems. Focus on identifying dependencies, infrastructure requirements, 
        potential downtime needs, and services that might be affected.
        """
        
        default_user_prompt = """
        Please analyze the following pull request and predict its deployment impact:
        
        # Pull Request Information
        - Title: {{title}}
        - Branch: {{branch}}
        - Description: {{description}}
        - Main Language: {{language}}
        
        # Code Changes
        ```diff
        {{diff}}
        ```
        
        # Commit Messages
        {{commit_messages_str}}
        
        Please provide a comprehensive deployment impact analysis including:
        
        1. System Dependency Analysis:
           - Identify affected components and services
           - Map code changes to infrastructure resources
           - Highlight configuration dependencies
        
        2. Change Impact Assessment:
           - Identify modified services, endpoints, or data models
           - Detect schema changes requiring migrations
           - Flag changes to performance-critical paths
        
        3. Deployment Requirements:
           - Estimate resource requirement changes (memory, CPU, storage)
           - Identify potential downtime requirements
           - List services requiring coordinated deployments
        
        4. Deployment Risk Score:
           - Provide a risk score (Low, Medium, High) with justification
           - Highlight specific concerns requiring extra attention
        
        5. Recommended Deployment Strategy:
           - Suggest the safest approach to deploy these changes
           - Recommend monitoring and rollback strategies
        
        {{extra_instructions}}
        """
        
        # Use settings if available, otherwise use defaults
        system_prompt = get_settings().pr_deployment_impact_prompt.system if hasattr(get_settings(), 'pr_deployment_impact_prompt') and hasattr(get_settings().pr_deployment_impact_prompt, 'system') else default_system_prompt
        user_prompt = get_settings().pr_deployment_impact_prompt.user if hasattr(get_settings(), 'pr_deployment_impact_prompt') and hasattr(get_settings().pr_deployment_impact_prompt, 'user') else default_user_prompt
        
        self.token_handler = TokenHandler(
            self.git_provider.pr,
            self.vars,
            system_prompt,
            user_prompt
        )
        
        self.progress = f"## Analyzing Deployment Impact\n\n"
        self.progress += f"""\nWork in progress ...<br>\n<img src="https://codium.ai/images/pr_agent/dual_ball_loading-crop.gif" width=48>"""

    async def run(self) -> None:
        """
        Run the deployment impact analysis on the PR.
        """
        try:
            if not self.git_provider.get_files():
                get_logger().info(f"PR has no files: {self.pr_url}, skipping deployment impact analysis")
                return None

            get_logger().info(f'Analyzing deployment impact for PR: {self.pr_url} ...')
            
            # Publish initial comment if configured to do so
            if get_settings().config.publish_output:
                self.git_provider.publish_comment(self.progress, is_temporary=True)

            # Generate the prediction
            await retry_with_fallback_models(self._prepare_prediction, model_type=ModelType.REGULAR)
            if not self.prediction:
                self.git_provider.remove_initial_comment()
                return None

            # Format and publish the deployment impact analysis
            deployment_impact_analysis = self._prepare_deployment_impact_analysis()
            get_logger().debug(f"Deployment impact analysis", artifact=deployment_impact_analysis)

            if get_settings().config.publish_output:
                # Publish the analysis
                if hasattr(get_settings(), 'pr_deployment_impact') and hasattr(get_settings().pr_deployment_impact, 'persistent_comment') and get_settings().pr_deployment_impact.persistent_comment:
                    final_update_message = get_settings().pr_deployment_impact.final_update_message if hasattr(get_settings().pr_deployment_impact, 'final_update_message') else ""
                    self.git_provider.publish_persistent_comment(
                        deployment_impact_analysis,
                        initial_header="## Deployment Impact Analysis 🚀",
                        update_header=True,
                        final_update_message=final_update_message,
                    )
                else:
                    self.git_provider.publish_comment(deployment_impact_analysis)

                self.git_provider.remove_initial_comment()
            else:
                get_logger().info("Deployment impact analysis output is not published")
                get_settings().data = {"artifact": deployment_impact_analysis}
                
                # Print the analysis to the console if in CLI mode
                if self.cli_mode:
                    print(deployment_impact_analysis)
                
        except Exception as e:
            get_logger().error(f"Failed to analyze deployment impact: {e}")
            get_logger().error(traceback.format_exc())
            try:
                if get_settings().config.publish_output:
                    self.git_provider.publish_comment(
                        "Failed to analyze deployment impact. See logs for more details."
                    )
                    self.git_provider.remove_initial_comment()
            except:
                pass

    async def _prepare_prediction(self, model: str) -> None:
        """
        Prepare the prediction by retrieving the PR diff and generating the deployment impact analysis.
        
        Args:
            model (str): The model to use for the prediction.
        """
        self.patches_diff = get_pr_diff(
            self.git_provider,
            self.token_handler,
            model,
            add_line_numbers_to_hunks=True,
            disable_extra_lines=False,
        )

        if self.patches_diff:
            get_logger().debug(f"PR diff", diff=self.patches_diff)
            self.prediction = await self._get_prediction(model)
        else:
            get_logger().warning(f"Empty diff for PR: {self.pr_url}")
            self.prediction = None

    async def _get_prediction(self, model: str) -> str:
        """
        Generate a prediction for the deployment impact using the AI model.
        
        Args:
            model (str): The model to use for the prediction.
            
        Returns:
            str: The prediction for the deployment impact.
        """
        # Update the vars with the diff
        self.vars["diff"] = self.patches_diff
        
        get_logger().info(f"Generating deployment impact analysis...")
        
        # Use settings if available, otherwise use defaults
        system_prompt = get_settings().pr_deployment_impact_prompt.system if hasattr(get_settings(), 'pr_deployment_impact_prompt') and hasattr(get_settings().pr_deployment_impact_prompt, 'system') else default_system_prompt
        user_prompt = get_settings().pr_deployment_impact_prompt.user if hasattr(get_settings(), 'pr_deployment_impact_prompt') and hasattr(get_settings().pr_deployment_impact_prompt, 'user') else default_user_prompt
        
        # Use Jinja2 templating to generate the prompt
        env = Environment(undefined=StrictUndefined)
        system_prompt_template = env.from_string(system_prompt)
        user_prompt_template = env.from_string(user_prompt)
        
        try:
            system_prompt = system_prompt_template.render(**self.vars)
            user_prompt = user_prompt_template.render(**self.vars)
        except Exception as e:
            get_logger().error(f"Error rendering prompt template: {e}")
            raise
        
        # Get the prediction from the AI model
        response, finish_reason = await self.ai_handler.chat_completion(
            system=system_prompt,
            user=user_prompt,
            model=model,
            temperature=get_settings().config.temperature,
        )
        
        return response

    def _prepare_deployment_impact_analysis(self) -> str:
        """
        Prepare the deployment impact analysis message to be published.
        
        Returns:
            str: The formatted deployment impact analysis.
        """
        deployment_impact_analysis = "# Deployment Impact Analysis 🚀\n\n"
        deployment_impact_analysis += self.prediction
        
        return deployment_impact_analysis
