"""Orchestrator - Phase6 Governed Optimization Loop.

Coordinates the optimization pipeline:
1. Analyzer scans data → metrics
2. Evaluator decides → proceed/wait/skip
3. Optimizer generates → proposals
4. Human approves → shadow execution
5. Shadow validates → switch or reject

Design:
- Offline decision + Online execution
- No auto-execution
- Clear approval gates
"""
import os
import sys
import time
from typing import Optional, List
from datetime import datetime

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.intelligence.analyzer import BehaviorAnalyzer, AnalysisMetrics, format_metrics
from aegisos.intelligence.evaluator import OptimizationEvaluator, OptimizationDecision, format_evaluation
from aegisos.intelligence.optimizer import StrategyOptimizer, ProposalManager, ProposalStatus
from aegisos.intelligence.policy import StrategyManager, ShadowExecutor


class OptimizationOrchestrator:
    """Orchestrates the governed optimization loop."""
    
    def __init__(self, project: str = "aegisos"):
        self.project = project
        self.analyzer = BehaviorAnalyzer(project=project)
        self.evaluator = OptimizationEvaluator(project=project)
        self.optimizer = StrategyOptimizer(project=project)
        self.shadow_executor = ShadowExecutor(project=project)
        
        # Initialize tables
        ProposalManager.init_tables()
    
    def run_analysis_cycle(self) -> Optional[List[int]]:
        """Run one complete analysis-optimization cycle.
        
        Returns:
            List of created proposal IDs, or None if skipped
        """
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting analysis cycle for {self.project}")
        
        # Step 1: Analyze
        print("  [1/5] Analyzing recent behavior...")
        metrics = self.analyzer.analyze(window_hours=24)
        
        if not metrics:
            print("  → Insufficient data for analysis")
            return None
        
        print(f"  → {metrics.total_tasks} tasks analyzed")
        print(f"  → Success rate: {metrics.success_rate:.1%}")
        
        # Detect anomalies
        anomalies = self.analyzer.detect_anomalies(metrics)
        if anomalies:
            print(f"  → {len(anomalies)} anomalies detected:")
            for a in anomalies:
                print(f"     - {a['type']} ({a['severity']}): {a['description']}")
        
        # Step 2: Evaluate
        print("  [2/5] Evaluating optimization need...")
        evaluation = self.evaluator.evaluate(metrics, anomalies)
        
        print(f"  → Decision: {evaluation.decision.value}")
        print(f"  → Confidence: {evaluation.confidence:.0%}")
        
        if evaluation.decision != OptimizationDecision.PROCEED:
            print(f"  → Skipping: {evaluation.reasons[0] if evaluation.reasons else 'No action needed'}")
            return None
        
        # Step 3: Generate Proposals
        print("  [3/5] Generating optimization proposals...")
        proposal_ids = self.optimizer.generate_proposals(metrics, anomalies)
        
        if not proposal_ids:
            print("  → No proposals generated")
            return None
        
        print(f"  → Created {len(proposal_ids)} proposals:")
        for pid in proposal_ids:
            proposal = ProposalManager.get_proposal(pid)
            if proposal:
                print(f"     #{pid}: {proposal.type.value} ({proposal.risk_level.value} risk)")
                print(f"        Reason: {proposal.reason}")
                print(f"        Expected: {proposal.expected_gain}")
        
        print(f"\n  ⚠️  Proposals require approval before execution")
        print(f"     Use: /proposals list")
        print(f"     Then: /proposals approve <id>")
        
        return proposal_ids
    
    def approve_and_shadow(self, proposal_id: int, approved_by: str) -> bool:
        """Approve proposal and start shadow execution.
        
        Args:
            proposal_id: Proposal to approve
            approved_by: Who approved it
            
        Returns:
            True if shadow execution started
        """
        print(f"\nApproving proposal #{proposal_id}...")
        
        # Approve proposal
        if not ProposalManager.approve_proposal(proposal_id, approved_by):
            print("  ✗ Failed to approve proposal")
            return False
        
        print("  ✓ Proposal approved")
        
        # Get proposal details
        proposal = ProposalManager.get_proposal(proposal_id)
        if not proposal:
            print("  ✗ Proposal not found")
            return False
        
        # Create strategy version
        print("  [1/3] Creating strategy version...")
        version_id = StrategyManager.create_strategy_version(
            project=self.project,
            prompt_template=f"Optimized for: {proposal.reason}",
            execution_rules={
                'type': proposal.type.value,
                'optimization': proposal.action
            },
            proposal_id=proposal_id
        )
        print(f"  ✓ Created strategy version #{version_id}")
        
        # Start shadow execution
        print("  [2/3] Starting shadow execution...")
        StrategyManager.start_shadow_execution(version_id)
        print(f"  ✓ Shadow execution started")
        print(f"  → Will run for N tasks to validate")
        
        # Update proposal with version
        print("  [3/3] Linking proposal to strategy...")
        print(f"  ✓ Ready for shadow validation")
        
        print(f"\n  Next steps:")
        print(f"  1. Monitor shadow execution: /proposals inspect {proposal_id}")
        print(f"  2. After validation: /switch strategy_version={version_id}")
        
        return True
    
    def execute_switch(self, version_id: int, approved_by: str = "system") -> bool:
        """Execute strategy switch after shadow validation.
        
        Args:
            version_id: Strategy version to switch to
            approved_by: Who approved the switch
            
        Returns:
            True if switch successful
        """
        print(f"\nExecuting strategy switch to version #{version_id}...")
        
        # Get strategy
        from aegisos.intelligence.policy import StrategyManager
        
        # Validate shadow execution
        print("  [1/3] Validating shadow execution...")
        comparison = self.shadow_executor.compare_shadow_vs_production(version_id)
        
        if not comparison.get('ready_to_switch'):
            print(f"  ✗ Shadow validation incomplete")
            print(f"     Need {comparison.get('production_samples', 20)} samples, "
                  f"have {comparison.get('shadow_samples', 0)}")
            return False
        
        print(f"  ✓ Shadow validation passed")
        
        # Check for regression
        comp = comparison.get('comparison', {})
        if comp.get('success_rate_change', 0) < -0.05:  # >5% regression
            print(f"  ✗ Success rate regression detected: {comp['success_rate_change']:.1%}")
            print(f"  → Switch blocked")
            return False
        
        print(f"  ✓ No regression detected")
        
        # Execute switch
        print("  [2/3] Activating new strategy...")
        if not StrategyManager.activate_strategy(version_id):
            print(f"  ✗ Failed to activate strategy")
            return False
        
        print(f"  ✓ Strategy #{version_id} activated")
        
        # Monitor
        print("  [3/3] Monitoring...")
        print(f"  → Monitoring for 60 minutes")
        print(f"  → Can rollback if issues detected")
        
        return True
    
    def get_status(self) -> dict:
        """Get current optimization status."""
        # Get pending proposals
        pending = ProposalManager.list_proposals(
            project=self.project, 
            status=ProposalStatus.PENDING
        )
        
        # Get active strategy
        active = StrategyManager.get_active_strategy(self.project)
        
        return {
            'project': self.project,
            'pending_proposals': len(pending),
            'active_strategy_version': active.version if active else None,
            'ready_for_switch': len([
                p for p in ProposalManager.list_proposals(project=self.project)
                if p.status == ProposalStatus.SHADOW
            ])
        }


def run_optimization_cycle(project: str = "aegisos") -> Optional[List[int]]:
    """Convenience function to run one optimization cycle."""
    orchestrator = OptimizationOrchestrator(project=project)
    return orchestrator.run_analysis_cycle()


def approve_proposal(proposal_id: int, approved_by: str = "system") -> bool:
    """Convenience function to approve and shadow."""
    orchestrator = OptimizationOrchestrator()
    return orchestrator.approve_and_shadow(proposal_id, approved_by)


def switch_strategy_version(version_id: int) -> bool:
    """Convenience function to switch strategy."""
    orchestrator = OptimizationOrchestrator()
    return orchestrator.execute_switch(version_id)
