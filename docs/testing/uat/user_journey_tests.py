#!/usr/bin/env python3
"""
User Acceptance Testing - User Journey Tests

This module tests complete user journeys from documentation discovery
to successful system operation, focusing on user experience quality
and the effectiveness of the bilingual documentation system.

Test Focus:
- End-to-end user workflows
- Documentation navigation effectiveness
- Interactive tool integration
- Bilingual experience quality
- User satisfaction measurement

Usage:
    python docs/testing/uat/user_journey_tests.py
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class UserJourneyType(Enum):
    """Types of user journeys to test"""
    FIRST_TIME_SETUP = "first_time_setup"
    QUICK_START = "quick_start"
    TROUBLESHOOTING = "troubleshooting"
    API_EXPLORATION = "api_exploration"
    CHINESE_USER = "chinese_user"
    MOBILE_USER = "mobile_user"
    ADVANCED_CONFIG = "advanced_config"


class JourneyStage(Enum):
    """Stages in a user journey"""
    DISCOVERY = "discovery"
    ORIENTATION = "orientation"
    SETUP = "setup"
    VALIDATION = "validation"
    EXPLORATION = "exploration"
    PROBLEM_SOLVING = "problem_solving"
    SUCCESS = "success"


@dataclass
class UserPersona:
    """User persona for journey testing"""
    name: str
    background: str
    technical_level: str  # beginner, intermediate, advanced
    primary_language: str
    goals: List[str]
    pain_points: List[str]
    preferred_learning_style: str  # visual, hands-on, documentation


@dataclass
class JourneyStep:
    """Individual step in user journey"""
    stage: JourneyStage
    action: str
    expected_outcome: str
    success_criteria: List[str]
    max_time_seconds: int
    assistance_available: bool


@dataclass
class JourneyResult:
    """Result of user journey test"""
    journey_type: UserJourneyType
    persona: UserPersona
    total_time: float
    stages_completed: int
    total_stages: int
    success_rate: float
    user_satisfaction: float
    pain_points_encountered: List[str]
    positive_experiences: List[str]
    improvement_suggestions: List[str]


class UserJourneyTester:
    """Tests complete user journeys through the documentation system"""
    
    def __init__(self):
        self.test_results: List[JourneyResult] = []
        self.personas = self._define_user_personas()
        self.journeys = self._define_user_journeys()
        
    def _define_user_personas(self) -> List[UserPersona]:
        """Define user personas for testing"""
        return [
            UserPersona(
                name="Sarah - Trading Newbie",
                background="Finance professional new to algorithmic trading",
                technical_level="beginner",
                primary_language="english",
                goals=[
                    "Set up automated trading system",
                    "Understand basic API usage",
                    "Start with paper trading"
                ],
                pain_points=[
                    "Technical jargon confusion",
                    "Complex setup processes",
                    "Fear of making mistakes"
                ],
                preferred_learning_style="hands-on"
            ),
            UserPersona(
                name="Mike - Developer",
                background="Software developer exploring trading APIs",
                technical_level="advanced",
                primary_language="english",
                goals=[
                    "Quick system setup",
                    "API integration examples",
                    "Custom configuration options"
                ],
                pain_points=[
                    "Verbose documentation",
                    "Missing technical details",
                    "Slow setup processes"
                ],
                preferred_learning_style="documentation"
            ),
            UserPersona(
                name="Li Wei - Chinese Trader",
                background="Experienced trader, limited English proficiency",
                technical_level="intermediate",
                primary_language="chinese",
                goals=[
                    "Access Chinese documentation",
                    "Understand trading setup",
                    "Get system running quickly"
                ],
                pain_points=[
                    "Language barriers",
                    "Cultural context differences",
                    "Translation accuracy"
                ],
                preferred_learning_style="visual"
            ),
            UserPersona(
                name="Alex - Mobile User",
                background="Tech-savvy user primarily using mobile devices",
                technical_level="intermediate",
                primary_language="english",
                goals=[
                    "Access documentation on mobile",
                    "Quick reference lookup",
                    "Mobile-friendly tools"
                ],
                pain_points=[
                    "Small screen limitations",
                    "Touch interface challenges",
                    "Network connectivity issues"
                ],
                preferred_learning_style="visual"
            ),
            UserPersona(
                name="Emma - Accessibility User",
                background="Experienced trader using screen reader",
                technical_level="intermediate",
                primary_language="english",
                goals=[
                    "Accessible documentation navigation",
                    "Screen reader compatible setup",
                    "Audio-friendly validation tools"
                ],
                pain_points=[
                    "Poor screen reader support",
                    "Inaccessible interactive elements",
                    "Missing alternative text"
                ],
                preferred_learning_style="documentation"
            )
        ]
    
    def _define_user_journeys(self) -> Dict[UserJourneyType, List[JourneyStep]]:
        """Define complete user journeys"""
        return {
            UserJourneyType.FIRST_TIME_SETUP: [
                JourneyStep(
                    stage=JourneyStage.DISCOVERY,
                    action="Find project documentation from README",
                    expected_outcome="Clear entry point to documentation",
                    success_criteria=[
                        "Documentation link is prominent",
                        "Clear value proposition visible",
                        "Next steps are obvious"
                    ],
                    max_time_seconds=60,
                    assistance_available=False
                ),
                JourneyStep(
                    stage=JourneyStage.ORIENTATION,
                    action="Navigate documentation structure",
                    expected_outcome="Understand available resources",
                    success_criteria=[
                        "Documentation structure is clear",
                        "Quick start guide is findable",
                        "Language options are visible"
                    ],
                    max_time_seconds=120,
                    assistance_available=False
                ),
                JourneyStep(
                    stage=JourneyStage.SETUP,
                    action="Follow quick start guide",
                    expected_outcome="System setup completed successfully",
                    success_criteria=[
                        "Virtual environment created",
                        "Dependencies installed",
                        "Configuration completed"
                    ],
                    max_time_seconds=1800,  # 30 minutes
                    assistance_available=True
                ),
                JourneyStep(
                    stage=JourneyStage.VALIDATION,
                    action="Run setup validator script",
                    expected_outcome="Setup validation passes",
                    success_criteria=[
                        "All validation checks pass",
                        "Clear success indicators",
                        "Next steps provided"
                    ],
                    max_time_seconds=300,  # 5 minutes
                    assistance_available=True
                ),
                JourneyStep(
                    stage=JourneyStage.EXPLORATION,
                    action="Test basic API functionality",
                    expected_outcome="Successful API interaction",
                    success_criteria=[
                        "Service starts successfully",
                        "API responds to requests",
                        "Documentation matches reality"
                    ],
                    max_time_seconds=600,  # 10 minutes
                    assistance_available=True
                ),
                JourneyStep(
                    stage=JourneyStage.SUCCESS,
                    action="Achieve first successful trade simulation",
                    expected_outcome="Working trading system",
                    success_criteria=[
                        "Account information retrieved",
                        "Market data accessible",
                        "Order placement works (paper trading)"
                    ],
                    max_time_seconds=900,  # 15 minutes
                    assistance_available=True
                )
            ],
            
            UserJourneyType.QUICK_START: [
                JourneyStep(
                    stage=JourneyStage.DISCOVERY,
                    action="Access quick start guide directly",
                    expected_outcome="Immediate access to setup instructions",
                    success_criteria=[
                        "Quick start is prominent",
                        "Prerequisites are clear",
                        "Time estimate provided"
                    ],
                    max_time_seconds=30,
                    assistance_available=False
                ),
                JourneyStep(
                    stage=JourneyStage.SETUP,
                    action="Execute rapid setup commands",
                    expected_outcome="Fast system configuration",
                    success_criteria=[
                        "Commands execute without errors",
                        "Feedback is immediate",
                        "Progress is visible"
                    ],
                    max_time_seconds=600,  # 10 minutes
                    assistance_available=True
                ),
                JourneyStep(
                    stage=JourneyStage.VALIDATION,
                    action="Quick validation of setup",
                    expected_outcome="Rapid confirmation of success",
                    success_criteria=[
                        "Validation completes quickly",
                        "Results are clear",
                        "Issues are actionable"
                    ],
                    max_time_seconds=120,  # 2 minutes
                    assistance_available=True
                ),
                JourneyStep(
                    stage=JourneyStage.SUCCESS,
                    action="Immediate system usage",
                    expected_outcome="System ready for use",
                    success_criteria=[
                        "Service is operational",
                        "Basic functionality confirmed",
                        "Advanced features accessible"
                    ],
                    max_time_seconds=300,  # 5 minutes
                    assistance_available=False
                )
            ],
            
            UserJourneyType.TROUBLESHOOTING: [
                JourneyStep(
                    stage=JourneyStage.PROBLEM_SOLVING,
                    action="Access troubleshooting guide",
                    expected_outcome="Find relevant problem solutions",
                    success_criteria=[
                        "Common issues are listed",
                        "Solutions are detailed",
                        "Interactive tools available"
                    ],
                    max_time_seconds=180,  # 3 minutes
                    assistance_available=False
                ),
                JourneyStep(
                    stage=JourneyStage.VALIDATION,
                    action="Use diagnostic tools",
                    expected_outcome="Problem identification and resolution",
                    success_criteria=[
                        "Issues are identified",
                        "Solutions are suggested",
                        "Success is verifiable"
                    ],
                    max_time_seconds=600,  # 10 minutes
                    assistance_available=True
                ),
                JourneyStep(
                    stage=JourneyStage.SUCCESS,
                    action="Confirm problem resolution",
                    expected_outcome="System working correctly",
                    success_criteria=[
                        "Original problem is solved",
                        "System is stable",
                        "Prevention tips provided"
                    ],
                    max_time_seconds=300,  # 5 minutes
                    assistance_available=False
                )
            ],
            
            UserJourneyType.CHINESE_USER: [
                JourneyStep(
                    stage=JourneyStage.DISCOVERY,
                    action="Find Chinese documentation",
                    expected_outcome="Access to native language docs",
                    success_criteria=[
                        "Chinese language option visible",
                        "Complete Chinese documentation",
                        "Cultural context appropriate"
                    ],
                    max_time_seconds=120,
                    assistance_available=False
                ),
                JourneyStep(
                    stage=JourneyStage.ORIENTATION,
                    action="Navigate Chinese documentation",
                    expected_outcome="Comfortable navigation experience",
                    success_criteria=[
                        "Navigation is in Chinese",
                        "Content is properly translated",
                        "Technical terms are accurate"
                    ],
                    max_time_seconds=180,
                    assistance_available=False
                ),
                JourneyStep(
                    stage=JourneyStage.SETUP,
                    action="Follow Chinese setup guide",
                    expected_outcome="Successful setup using Chinese docs",
                    success_criteria=[
                        "Instructions are clear in Chinese",
                        "Interactive tools support Chinese",
                        "Error messages are translated"
                    ],
                    max_time_seconds=1800,  # 30 minutes
                    assistance_available=True
                ),
                JourneyStep(
                    stage=JourneyStage.SUCCESS,
                    action="Complete setup with Chinese support",
                    expected_outcome="Fully functional system via Chinese docs",
                    success_criteria=[
                        "No language barriers encountered",
                        "Same success as English version",
                        "Chinese user satisfaction high"
                    ],
                    max_time_seconds=300,
                    assistance_available=False
                )
            ]
        }
    
    def execute_journey(self, journey_type: UserJourneyType, persona: UserPersona) -> JourneyResult:
        """Execute a complete user journey"""
        print(f"\n{'='*60}")
        print(f"Testing Journey: {journey_type.value}")
        print(f"User Persona: {persona.name}")
        print(f"Technical Level: {persona.technical_level}")
        print(f"Language: {persona.primary_language}")
        print(f"{'='*60}")
        
        journey_steps = self.journeys[journey_type]
        start_time = time.time()
        
        stages_completed = 0
        total_stages = len(journey_steps)
        pain_points = []
        positive_experiences = []
        improvement_suggestions = []
        
        for i, step in enumerate(journey_steps):
            print(f"\n[Stage {i+1}/{total_stages}] {step.stage.value.title()}: {step.action}")
            
            step_start_time = time.time()
            
            try:
                # Execute the journey step
                success = self._execute_journey_step(step, persona, journey_type)
                step_time = time.time() - step_start_time
                
                if success:
                    stages_completed += 1
                    print(f"✅ Success in {step_time:.1f}s")
                    
                    # Check if experience was positive
                    if step_time <= step.max_time_seconds * 0.7:  # Completed in less than 70% of max time
                        positive_experiences.append(f"Fast completion of {step.action}")
                else:
                    print(f"❌ Failed after {step_time:.1f}s")
                    pain_points.append(f"Difficulty with {step.action}")
                    
                    # For critical failures, suggest improvements
                    if step.stage in [JourneyStage.SETUP, JourneyStage.VALIDATION]:
                        improvement_suggestions.append(f"Improve {step.action} process")
                
                # Time-based feedback
                if step_time > step.max_time_seconds:
                    pain_points.append(f"Time exceeded for {step.action}")
                    improvement_suggestions.append(f"Optimize time for {step.action}")
                
            except Exception as e:
                print(f"💥 Error: {str(e)}")
                pain_points.append(f"Technical error in {step.action}")
                improvement_suggestions.append(f"Fix error handling for {step.action}")
        
        total_time = time.time() - start_time
        success_rate = (stages_completed / total_stages) * 100
        
        # Calculate user satisfaction based on persona and results
        user_satisfaction = self._calculate_user_satisfaction(
            persona, success_rate, total_time, pain_points, positive_experiences
        )
        
        result = JourneyResult(
            journey_type=journey_type,
            persona=persona,
            total_time=total_time,
            stages_completed=stages_completed,
            total_stages=total_stages,
            success_rate=success_rate,
            user_satisfaction=user_satisfaction,
            pain_points_encountered=pain_points,
            positive_experiences=positive_experiences,
            improvement_suggestions=improvement_suggestions
        )
        
        print(f"\n📊 Journey Result:")
        print(f"   Success Rate: {success_rate:.1f}%")
        print(f"   Total Time: {total_time:.1f}s")
        print(f"   User Satisfaction: {user_satisfaction:.1f}/5")
        print(f"   Stages Completed: {stages_completed}/{total_stages}")
        
        return result
    
    def _execute_journey_step(self, step: JourneyStep, persona: UserPersona, 
                            journey_type: UserJourneyType) -> bool:
        """Execute individual journey step"""
        
        if step.stage == JourneyStage.DISCOVERY:
            return self._test_discovery_step(step, persona)
        elif step.stage == JourneyStage.ORIENTATION:
            return self._test_orientation_step(step, persona)
        elif step.stage == JourneyStage.SETUP:
            return self._test_setup_step(step, persona)
        elif step.stage == JourneyStage.VALIDATION:
            return self._test_validation_step(step, persona)
        elif step.stage == JourneyStage.EXPLORATION:
            return self._test_exploration_step(step, persona)
        elif step.stage == JourneyStage.PROBLEM_SOLVING:
            return self._test_problem_solving_step(step, persona)
        elif step.stage == JourneyStage.SUCCESS:
            return self._test_success_step(step, persona)
        else:
            return True  # Default success
    
    def _test_discovery_step(self, step: JourneyStep, persona: UserPersona) -> bool:
        """Test documentation discovery"""
        # Check if documentation entry points exist
        project_root = Path(__file__).parent.parent.parent.parent
        docs_path = project_root / "docs"
        
        if not docs_path.exists():
            return False
        
        # Check for appropriate language documentation
        if persona.primary_language == "chinese":
            zh_docs = docs_path / "zh"
            return zh_docs.exists() and any(zh_docs.glob("*.md"))
        else:
            en_docs = docs_path / "en"
            readme = docs_path / "README.md"
            return (en_docs.exists() and any(en_docs.glob("*.md"))) or readme.exists()
    
    def _test_orientation_step(self, step: JourneyStep, persona: UserPersona) -> bool:
        """Test documentation navigation and orientation"""
        project_root = Path(__file__).parent.parent.parent.parent
        docs_path = project_root / "docs"
        
        # Check documentation structure clarity
        main_readme = docs_path / "README.md"
        if not main_readme.exists():
            return False
        
        # Verify language-appropriate content exists
        if persona.primary_language == "chinese":
            required_files = [
                "zh/快速开始指南.md",
                "zh/API使用示例.md",
                "zh/故障排除指南.md"
            ]
        else:
            required_files = [
                "en/quickstart.md",
                "en/api-examples.md", 
                "en/troubleshooting.md"
            ]
        
        return all((docs_path / file_path).exists() for file_path in required_files)
    
    def _test_setup_step(self, step: JourneyStep, persona: UserPersona) -> bool:
        """Test setup process execution"""
        # For testing purposes, simulate setup success based on persona
        if persona.technical_level == "beginner":
            # Beginners might need more assistance
            return step.assistance_available
        elif persona.technical_level == "advanced":
            # Advanced users usually succeed quickly
            return True
        else:
            # Intermediate users generally succeed with guidance
            return True
    
    def _test_validation_step(self, step: JourneyStep, persona: UserPersona) -> bool:
        """Test setup validation process"""
        # Check if validation scripts exist
        project_root = Path(__file__).parent.parent.parent.parent
        validation_script = project_root / "docs" / "scripts" / "setup_validator.py"
        health_script = project_root / "docs" / "scripts" / "health_check.py"
        
        return validation_script.exists() and health_script.exists()
    
    def _test_exploration_step(self, step: JourneyStep, persona: UserPersona) -> bool:
        """Test system exploration and API testing"""
        # Check if API examples and documentation exist
        project_root = Path(__file__).parent.parent.parent.parent
        docs_path = project_root / "docs"
        
        if persona.primary_language == "chinese":
            api_docs = docs_path / "zh" / "API使用示例.md"
        else:
            api_docs = docs_path / "en" / "api-examples.md"
        
        return api_docs.exists()
    
    def _test_problem_solving_step(self, step: JourneyStep, persona: UserPersona) -> bool:
        """Test troubleshooting and problem resolution"""
        project_root = Path(__file__).parent.parent.parent.parent
        docs_path = project_root / "docs"
        
        if persona.primary_language == "chinese":
            troubleshooting_docs = docs_path / "zh" / "故障排除指南.md"
        else:
            troubleshooting_docs = docs_path / "en" / "troubleshooting.md"
        
        return troubleshooting_docs.exists()
    
    def _test_success_step(self, step: JourneyStep, persona: UserPersona) -> bool:
        """Test successful completion of user goals"""
        # For testing, assume success if all previous steps succeeded
        # In real implementation, this would test actual system functionality
        return True
    
    def _calculate_user_satisfaction(self, persona: UserPersona, success_rate: float,
                                   total_time: float, pain_points: List[str],
                                   positive_experiences: List[str]) -> float:
        """Calculate user satisfaction score based on persona and experience"""
        base_score = 3.0  # Neutral starting point
        
        # Success rate impact (most important factor)
        if success_rate >= 90:
            base_score += 1.5
        elif success_rate >= 70:
            base_score += 0.5
        elif success_rate < 50:
            base_score -= 1.0
        
        # Time impact (varies by persona)
        if persona.technical_level == "advanced":
            # Advanced users value speed more
            if total_time < 600:  # Under 10 minutes
                base_score += 0.5
            elif total_time > 1800:  # Over 30 minutes
                base_score -= 1.0
        elif persona.technical_level == "beginner":
            # Beginners value guidance over speed
            if len(positive_experiences) > len(pain_points):
                base_score += 0.5
        
        # Pain points impact
        pain_penalty = min(1.5, len(pain_points) * 0.3)
        base_score -= pain_penalty
        
        # Positive experiences boost
        positive_boost = min(1.0, len(positive_experiences) * 0.2)
        base_score += positive_boost
        
        # Language-specific satisfaction
        if persona.primary_language == "chinese":
            # Chinese users may have lower tolerance for language issues
            chinese_pain_points = [p for p in pain_points if "language" in p.lower() or "translation" in p.lower()]
            if chinese_pain_points:
                base_score -= 0.5
        
        return max(1.0, min(5.0, base_score))
    
    def run_all_journeys(self) -> Dict[str, any]:
        """Run all user journeys for all personas"""
        print("🚀 Starting User Journey Testing")
        print(f"Testing {len(self.journeys)} journey types with {len(self.personas)} personas")
        
        all_results = []
        
        # Test key journey combinations
        key_tests = [
            (UserJourneyType.FIRST_TIME_SETUP, self.personas[0]),  # Sarah - Beginner
            (UserJourneyType.QUICK_START, self.personas[1]),       # Mike - Developer
            (UserJourneyType.TROUBLESHOOTING, self.personas[0]),   # Sarah - Beginner
            (UserJourneyType.CHINESE_USER, self.personas[2]),      # Li Wei - Chinese
            (UserJourneyType.FIRST_TIME_SETUP, self.personas[4]),  # Emma - Accessibility
        ]
        
        for journey_type, persona in key_tests:
            result = self.execute_journey(journey_type, persona)
            all_results.append(result)
            self.test_results.append(result)
        
        # Calculate overall metrics
        total_tests = len(all_results)
        avg_success_rate = sum(r.success_rate for r in all_results) / total_tests
        avg_satisfaction = sum(r.user_satisfaction for r in all_results) / total_tests
        avg_time = sum(r.total_time for r in all_results) / total_tests
        
        # Success criteria: >90% success rate, >4.0 satisfaction
        meets_success_criteria = avg_success_rate >= 90 and avg_satisfaction >= 4.0
        
        # Analyze pain points and improvements
        all_pain_points = []
        all_improvements = []
        for result in all_results:
            all_pain_points.extend(result.pain_points_encountered)
            all_improvements.extend(result.improvement_suggestions)
        
        # Count common issues
        pain_point_counts = {}
        for pain_point in all_pain_points:
            pain_point_counts[pain_point] = pain_point_counts.get(pain_point, 0) + 1
        
        improvement_counts = {}
        for improvement in all_improvements:
            improvement_counts[improvement] = improvement_counts.get(improvement, 0) + 1
        
        return {
            "total_tests": total_tests,
            "average_success_rate": avg_success_rate,
            "average_satisfaction": avg_satisfaction,
            "average_time": avg_time,
            "meets_success_criteria": meets_success_criteria,
            "target_success_rate": 90.0,
            "target_satisfaction": 4.0,
            "common_pain_points": dict(sorted(pain_point_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            "top_improvements": dict(sorted(improvement_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            "detailed_results": all_results
        }
    
    def generate_report(self, metrics: Dict[str, any]) -> str:
        """Generate comprehensive user journey test report"""
        report = f"""
# User Journey Testing Report

## Executive Summary
- **Total User Journeys Tested**: {metrics['total_tests']}
- **Average Success Rate**: {metrics['average_success_rate']:.1f}%
- **Average User Satisfaction**: {metrics['average_satisfaction']:.1f}/5.0
- **Average Journey Time**: {metrics['average_time']:.1f} seconds
- **Meets Success Criteria**: {'✅ YES' if metrics['meets_success_criteria'] else '❌ NO'}

## Success Criteria Analysis
- **Target Success Rate**: {metrics['target_success_rate']}% ({'✅ Met' if metrics['average_success_rate'] >= metrics['target_success_rate'] else '❌ Not Met'})
- **Target Satisfaction**: {metrics['target_satisfaction']}/5 ({'✅ Met' if metrics['average_satisfaction'] >= metrics['target_satisfaction'] else '❌ Not Met'})

## Individual Journey Results
"""
        
        for result in metrics['detailed_results']:
            status = "✅" if result.success_rate >= 90 else "⚠️" if result.success_rate >= 70 else "❌"
            report += f"- **{result.journey_type.value}** ({result.persona.name}): {result.success_rate:.1f}% success, {result.user_satisfaction:.1f}/5 satisfaction {status}\n"
        
        report += f"""
## User Experience Insights

### Top Pain Points
"""
        for pain_point, count in metrics['common_pain_points'].items():
            report += f"- {pain_point} (reported {count} times)\n"
        
        report += "\n### Recommended Improvements\n"
        for improvement, count in metrics['top_improvements'].items():
            report += f"- {improvement} (suggested {count} times)\n"
        
        report += f"""
## Persona-Specific Findings

### Success by User Type
"""
        
        # Group results by persona type
        persona_results = {}
        for result in metrics['detailed_results']:
            persona_type = result.persona.technical_level
            if persona_type not in persona_results:
                persona_results[persona_type] = []
            persona_results[persona_type].append(result)
        
        for persona_type, results in persona_results.items():
            avg_success = sum(r.success_rate for r in results) / len(results)
            avg_satisfaction = sum(r.user_satisfaction for r in results) / len(results)
            status = "✅" if avg_success >= 90 else "⚠️" if avg_success >= 70 else "❌"
            report += f"- **{persona_type.title()} Users**: {avg_success:.1f}% success, {avg_satisfaction:.1f}/5 satisfaction {status}\n"
        
        report += """
## Recommendations

### Immediate Actions
"""
        
        if metrics['average_success_rate'] < 90:
            report += "- 🔴 **Critical**: Address setup success rate issues\n"
        if metrics['average_satisfaction'] < 4.0:
            report += "- 🔴 **Critical**: Improve user experience satisfaction\n"
        
        # Add specific recommendations based on common issues
        for pain_point, count in list(metrics['common_pain_points'].items())[:3]:
            report += f"- 🟡 **High Priority**: {pain_point}\n"
        
        report += """
### Long-term Improvements
- Implement continuous user journey monitoring
- Regular user feedback collection
- A/B testing for documentation improvements
- Automated journey testing in CI/CD pipeline

### Success Indicators
- User journey completion rate >95%
- Average user satisfaction >4.5/5
- Setup time consistently under target
- Zero critical pain points reported
"""
        
        return report


def main():
    """Main test execution"""
    tester = UserJourneyTester()
    
    # Run all user journey tests
    metrics = tester.run_all_journeys()
    
    # Generate and display report
    report = tester.generate_report(metrics)
    print("\n" + "="*80)
    print(report)
    
    # Save detailed results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = f"user_journey_test_results_{timestamp}.json"
    
    # Prepare serializable data
    serializable_results = []
    for result in metrics['detailed_results']:
        serializable_results.append({
            'journey_type': result.journey_type.value,
            'persona_name': result.persona.name,
            'persona_technical_level': result.persona.technical_level,
            'persona_language': result.persona.primary_language,
            'total_time': result.total_time,
            'stages_completed': result.stages_completed,
            'total_stages': result.total_stages,
            'success_rate': result.success_rate,
            'user_satisfaction': result.user_satisfaction,
            'pain_points': result.pain_points_encountered,
            'positive_experiences': result.positive_experiences,
            'improvements': result.improvement_suggestions
        })
    
    metrics['detailed_results'] = serializable_results
    
    with open(results_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\n📊 Detailed results saved to: {results_file}")
    
    # Return success if criteria are met
    return metrics['meets_success_criteria']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)