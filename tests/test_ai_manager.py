"""Tests for AI manager module."""
import pytest

from backend.ai_manager import (
    TaskAnalysis,
    TaskBatchAnalysis,
    analyze_task_batch,
    analyze_task_complexity,
    format_analysis_for_display,
    format_batch_analysis_for_display,
)


class TestTaskAnalysis:
    """Tests for TaskAnalysis model."""

    def test_create_task_analysis(self):
        """Test creating a TaskAnalysis instance."""
        analysis = TaskAnalysis(
            should_split=True,
            suggested_subtasks=[
                {"title": "Subtask 1", "description": "First subtask"},
                {"title": "Subtask 2", "description": "Second subtask"},
            ],
            suggested_priority="high",
            suggested_tags=["backend", "api"],
            complexity_score=8,
            estimated_hours=4.5,
            reasoning="This task is complex and should be split.",
        )

        assert analysis.should_split is True
        assert len(analysis.suggested_subtasks) == 2
        assert analysis.suggested_priority == "high"
        assert analysis.complexity_score == 8
        assert analysis.estimated_hours == 4.5

    def test_task_analysis_defaults(self):
        """Test TaskAnalysis with minimal fields."""
        analysis = TaskAnalysis(
            should_split=False,
            suggested_priority="normal",
            suggested_tags=[],
            complexity_score=3,
            estimated_hours=1.0,
            reasoning="Simple task.",
        )

        assert analysis.suggested_subtasks == []


class TestTaskBatchAnalysis:
    """Tests for TaskBatchAnalysis model."""

    def test_create_batch_analysis(self):
        """Test creating a TaskBatchAnalysis instance."""
        analysis = TaskBatchAnalysis(
            priority_updates=[
                {"task_id": "T-001", "new_priority": "high", "reason": "Critical bug"},
            ],
            tag_updates=[
                {"task_id": "T-002", "add_tags": ["urgent"], "remove_tags": []},
            ],
            suggested_order=["T-001", "T-003", "T-002"],
            insights="Focus on bugs first.",
        )

        assert len(analysis.priority_updates) == 1
        assert len(analysis.tag_updates) == 1
        assert analysis.suggested_order == ["T-001", "T-003", "T-002"]


class TestAnalyzeTaskComplexity:
    """Tests for analyze_task_complexity function."""

    @pytest.mark.asyncio
    async def test_analyze_without_api_key(self, monkeypatch):
        """Test that analysis returns defaults when no API key is set."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        result = await analyze_task_complexity(
            title="Test task",
            description="A simple test task",
            tags=["test"],
        )

        assert isinstance(result, TaskAnalysis)
        assert result.should_split is False
        assert result.suggested_priority == "normal"
        assert result.suggested_tags == ["test"]
        assert result.complexity_score == 5
        assert result.estimated_hours == 2.0
        assert "No API key" in result.reasoning

    @pytest.mark.asyncio
    async def test_analyze_preserves_tags(self, monkeypatch):
        """Test that existing tags are preserved in fallback."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        tags = ["backend", "urgent", "api"]
        result = await analyze_task_complexity(
            title="Complex task",
            description="Description",
            tags=tags,
        )

        assert result.suggested_tags == tags

    @pytest.mark.asyncio
    async def test_analyze_with_none_tags(self, monkeypatch):
        """Test analysis with None tags."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        result = await analyze_task_complexity(
            title="Task",
            description="Description",
            tags=None,
        )

        assert result.suggested_tags == []


class TestAnalyzeTaskBatch:
    """Tests for analyze_task_batch function."""

    @pytest.mark.asyncio
    async def test_batch_analyze_without_api_key(self, monkeypatch):
        """Test batch analysis returns defaults without API key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        tasks = [
            {"id": "T-001", "title": "Task 1"},
            {"id": "T-002", "title": "Task 2"},
            {"id": "T-003", "title": "Task 3"},
        ]

        result = await analyze_task_batch(tasks)

        assert isinstance(result, TaskBatchAnalysis)
        assert result.priority_updates == []
        assert result.tag_updates == []
        assert result.suggested_order == ["T-001", "T-002", "T-003"]
        assert "No API key" in result.insights

    @pytest.mark.asyncio
    async def test_batch_analyze_preserves_order(self, monkeypatch):
        """Test that original task order is preserved in fallback."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        tasks = [
            {"id": "Z-999", "title": "Last"},
            {"id": "A-001", "title": "First"},
            {"id": "M-500", "title": "Middle"},
        ]

        result = await analyze_task_batch(tasks)

        assert result.suggested_order == ["Z-999", "A-001", "M-500"]

    @pytest.mark.asyncio
    async def test_batch_analyze_with_goal(self, monkeypatch):
        """Test batch analysis with custom goal."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        tasks = [{"id": "T-001", "title": "Task"}]

        result = await analyze_task_batch(tasks, goal="Quick wins first")

        assert isinstance(result, TaskBatchAnalysis)


class TestFormatAnalysisForDisplay:
    """Tests for format_analysis_for_display function."""

    def test_format_simple_analysis(self):
        """Test formatting a simple analysis."""
        analysis = TaskAnalysis(
            should_split=False,
            suggested_priority="normal",
            suggested_tags=["backend"],
            complexity_score=5,
            estimated_hours=2.0,
            reasoning="This is a straightforward task.",
        )

        output = format_analysis_for_display(analysis)

        assert "Task Analysis" in output
        assert "NORMAL" in output
        assert "5/13" in output
        assert "2.0 hours" in output
        assert "#backend" in output
        assert "straightforward" in output

    def test_format_analysis_with_split_recommendation(self):
        """Test formatting an analysis that recommends splitting."""
        analysis = TaskAnalysis(
            should_split=True,
            suggested_subtasks=[
                {"title": "Design API", "description": "Plan the API structure"},
                {"title": "Implement endpoints", "description": "Code the endpoints"},
                {"title": "Write tests", "description": "Add unit tests"},
            ],
            suggested_priority="high",
            suggested_tags=["backend", "api"],
            complexity_score=13,
            estimated_hours=8.0,
            reasoning="This task is too complex for a single unit of work.",
        )

        output = format_analysis_for_display(analysis)

        assert "SPLIT THIS TASK" in output
        assert "Design API" in output
        assert "Implement endpoints" in output
        assert "Write tests" in output
        assert "3" in output  # Number of subtasks

    def test_format_analysis_multiple_tags(self):
        """Test formatting with multiple tags."""
        analysis = TaskAnalysis(
            should_split=False,
            suggested_priority="critical",
            suggested_tags=["security", "urgent", "backend"],
            complexity_score=8,
            estimated_hours=4.0,
            reasoning="Security issue needs attention.",
        )

        output = format_analysis_for_display(analysis)

        assert "#security" in output
        assert "#urgent" in output
        assert "#backend" in output

    def test_format_analysis_no_tags(self):
        """Test formatting with no tags."""
        analysis = TaskAnalysis(
            should_split=False,
            suggested_priority="low",
            suggested_tags=[],
            complexity_score=1,
            estimated_hours=0.5,
            reasoning="Trivial task.",
        )

        output = format_analysis_for_display(analysis)

        assert "LOW" in output


class TestFormatBatchAnalysisForDisplay:
    """Tests for format_batch_analysis_for_display function."""

    def test_format_batch_with_updates(self):
        """Test formatting batch analysis with updates."""
        analysis = TaskBatchAnalysis(
            priority_updates=[
                {"task_id": "T-001", "new_priority": "critical", "reason": "Bug is blocking"},
                {"task_id": "T-002", "new_priority": "high", "reason": "Customer request"},
            ],
            tag_updates=[
                {"task_id": "T-003", "add_tags": ["urgent"], "remove_tags": ["low-priority"]},
            ],
            suggested_order=["T-001", "T-002", "T-003", "T-004", "T-005"],
            insights="Focus on critical bugs first, then customer requests.",
        )

        output = format_batch_analysis_for_display(analysis)

        assert "Batch Analysis" in output
        assert "Priority Updates" in output
        assert "T-001" in output
        assert "critical" in output
        assert "Tag Updates" in output
        assert "urgent" in output
        assert "Recommended Order" in output
        assert "Focus on critical bugs" in output

    def test_format_batch_empty_updates(self):
        """Test formatting batch analysis with no updates."""
        analysis = TaskBatchAnalysis(
            priority_updates=[],
            tag_updates=[],
            suggested_order=["T-001", "T-002"],
            insights="Everything looks good.",
        )

        output = format_batch_analysis_for_display(analysis)

        assert "Everything looks good" in output
        assert "Recommended Order" in output

    def test_format_batch_many_tasks(self):
        """Test formatting batch with many tasks (truncation)."""
        analysis = TaskBatchAnalysis(
            priority_updates=[],
            tag_updates=[],
            suggested_order=[f"T-{i:03d}" for i in range(20)],
            insights="Large backlog analysis.",
        )

        output = format_batch_analysis_for_display(analysis)

        # Should show first 10 and indicate more
        assert "T-000" in output
        assert "T-009" in output
        assert "10 more" in output

    def test_format_batch_tag_additions_and_removals(self):
        """Test formatting tag additions and removals."""
        analysis = TaskBatchAnalysis(
            priority_updates=[],
            tag_updates=[
                {"task_id": "T-001", "add_tags": ["new-tag"], "remove_tags": []},
                {"task_id": "T-002", "add_tags": [], "remove_tags": ["old-tag"]},
            ],
            suggested_order=["T-001", "T-002"],
            insights="Tag cleanup.",
        )

        output = format_batch_analysis_for_display(analysis)

        assert "new-tag" in output
        assert "old-tag" in output
