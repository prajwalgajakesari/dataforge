"""
Workspace Manager for DataForge.

This module handles all file system operations and git integration for DataForge workspaces.
Each workspace is a self-contained project directory with version control.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import git
from pydantic import BaseModel, Field


class WorkspaceConfig(BaseModel):
    """Configuration for a workspace."""

    workspace_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    path: Path
    project_type: str  # dbt, airflow, terraform, multi
    git_repo: Optional[str] = None
    git_branch: str = "main"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


class WorkspaceManager:
    """
    Manages file system operations and git integration for DataForge workspaces.

    Each workspace is a self-contained project directory containing:
    - Generated code (dbt, airflow, terraform)
    - Documentation
    - Configuration files
    - Git repository

    The workspace manager provides:
    - Workspace lifecycle (create, load, delete)
    - File operations (read, write, delete, list)
    - Git operations (init, commit, branch, push)
    - Template application
    - State persistence
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize the workspace manager.

        Args:
            base_path: Base directory for all workspaces
        """
        if base_path:
            self.base_path = Path(base_path).expanduser().resolve()
        else:
            # Honour DATAFORGE_WORKSPACE_DIR (default: ~/dataforge-workspaces)
            from core.utils.config import settings

            self.base_path = settings.get_workspace_path()

        self.base_path.mkdir(parents=True, exist_ok=True)
        self.current_workspace: Optional[WorkspaceConfig] = None
        self.metadata_file = self.base_path / ".workspace_metadata.json"
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load workspace metadata from disk."""
        if not self.metadata_file.exists():
            self._workspaces = {}
            return

        try:
            with open(self.metadata_file, "r") as f:
                data = json.load(f)
                self._workspaces = {k: WorkspaceConfig(**v) for k, v in data.items()}
        except Exception as e:
            print(f"Error loading workspace metadata: {e}")
            self._workspaces = {}

    def _save_metadata(self) -> None:
        """Save workspace metadata to disk."""
        try:
            data = {
                k: json.loads(v.model_dump_json())
                for k, v in self._workspaces.items()
            }
            # Convert Path objects to strings for JSON serialization
            for workspace_data in data.values():
                if "path" in workspace_data and isinstance(workspace_data["path"], Path):
                    workspace_data["path"] = str(workspace_data["path"])

            with open(self.metadata_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving workspace metadata: {e}")

    def create_workspace(
        self,
        name: str,
        project_type: str,
        template: Optional[str] = None
    ) -> WorkspaceConfig:
        """
        Create a new workspace from template.

        Args:
            name: Name of the workspace
            project_type: Type of project (dbt, airflow, terraform, multi)
            template: Optional template to use

        Returns:
            WorkspaceConfig for the new workspace

        Raises:
            ValueError: If workspace already exists
        """
        # Sanitize name for directory
        dir_name = name.lower().replace(" ", "_").replace("-", "_")
        workspace_path = self.base_path / dir_name

        if workspace_path.exists():
            raise ValueError(f"Workspace '{name}' already exists at {workspace_path}")

        # Create directory
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Create workspace config
        config = WorkspaceConfig(
            name=name,
            path=workspace_path,
            project_type=project_type,
        )

        # Apply template if specified
        if template:
            self._apply_template(workspace_path, template)

        # Initialize git repository
        self._init_git(workspace_path)

        # Save workspace config
        self._workspaces[config.workspace_id] = config
        self._save_metadata()

        # Set as current workspace
        self.current_workspace = config

        return config

    def load_workspace(self, workspace_id: str) -> WorkspaceConfig:
        """
        Load an existing workspace.

        Args:
            workspace_id: ID of the workspace to load

        Returns:
            WorkspaceConfig

        Raises:
            ValueError: If workspace not found
        """
        if workspace_id not in self._workspaces:
            raise ValueError(f"Workspace {workspace_id} not found")

        config = self._workspaces[workspace_id]
        self.current_workspace = config
        return config

    def list_workspaces(self) -> List[WorkspaceConfig]:
        """
        List all available workspaces.

        Returns:
            List of workspace configurations
        """
        return list(self._workspaces.values())

    def delete_workspace(self, workspace_id: str, confirm: bool = False) -> None:
        """
        Delete a workspace.

        Args:
            workspace_id: ID of workspace to delete
            confirm: Must be True to actually delete

        Raises:
            ValueError: If workspace not found or confirm not True
        """
        if not confirm:
            raise ValueError("Must set confirm=True to delete workspace")

        if workspace_id not in self._workspaces:
            raise ValueError(f"Workspace {workspace_id} not found")

        config = self._workspaces[workspace_id]

        # Remove from disk
        if config.path.exists():
            shutil.rmtree(config.path)

        # Remove from metadata
        del self._workspaces[workspace_id]
        self._save_metadata()

        # Clear current workspace if it was deleted
        if self.current_workspace and self.current_workspace.workspace_id == workspace_id:
            self.current_workspace = None

    def write_file(
        self,
        relative_path: str,
        content: str,
        auto_commit: bool = False
    ) -> Path:
        """
        Write a file to the current workspace.

        Args:
            relative_path: Path relative to workspace root
            content: File content
            auto_commit: Whether to automatically commit the file

        Returns:
            Absolute path to the written file

        Raises:
            ValueError: If no workspace is loaded
        """
        if not self.current_workspace:
            raise ValueError("No workspace loaded")

        file_path = self.current_workspace.path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            f.write(content)

        if auto_commit:
            self.git_commit(f"Add {relative_path}", files=[str(relative_path)])

        return file_path

    def read_file(self, relative_path: str) -> str:
        """
        Read a file from the current workspace.

        Args:
            relative_path: Path relative to workspace root

        Returns:
            File content

        Raises:
            ValueError: If no workspace is loaded
            FileNotFoundError: If file doesn't exist
        """
        if not self.current_workspace:
            raise ValueError("No workspace loaded")

        file_path = self.current_workspace.path / relative_path

        if not file_path.exists():
            raise FileNotFoundError(f"File {relative_path} not found")

        with open(file_path, "r") as f:
            return f.read()

    def delete_file(self, relative_path: str) -> None:
        """
        Delete a file from the current workspace.

        Args:
            relative_path: Path relative to workspace root

        Raises:
            ValueError: If no workspace is loaded
        """
        if not self.current_workspace:
            raise ValueError("No workspace loaded")

        file_path = self.current_workspace.path / relative_path

        if file_path.exists():
            file_path.unlink()

    def list_files(
        self,
        pattern: Optional[str] = None,
        recursive: bool = True
    ) -> List[Path]:
        """
        List files in the current workspace.

        Args:
            pattern: Optional glob pattern to filter files
            recursive: Whether to search recursively

        Returns:
            List of file paths

        Raises:
            ValueError: If no workspace is loaded
        """
        if not self.current_workspace:
            raise ValueError("No workspace loaded")

        if pattern:
            if recursive:
                files = list(self.current_workspace.path.rglob(pattern))
            else:
                files = list(self.current_workspace.path.glob(pattern))
        else:
            if recursive:
                files = [
                    f for f in self.current_workspace.path.rglob("*")
                    if f.is_file()
                ]
            else:
                files = [
                    f for f in self.current_workspace.path.glob("*")
                    if f.is_file()
                ]

        return files

    def _init_git(self, workspace_path: Path) -> git.Repo:
        """
        Initialize a git repository in the workspace.

        Args:
            workspace_path: Path to workspace

        Returns:
            Git repository object
        """
        repo = git.Repo.init(workspace_path)

        # Create .gitignore
        gitignore_path = workspace_path / ".gitignore"
        with open(gitignore_path, "w") as f:
            f.write(
                "# Python\n"
                "__pycache__/\n"
                "*.py[cod]\n"
                ".venv/\n"
                "venv/\n"
                "\n"
                "# dbt\n"
                "target/\n"
                "dbt_packages/\n"
                "logs/\n"
                "\n"
                "# Environment\n"
                ".env\n"
                ".env.local\n"
            )

        # Initial commit
        repo.index.add([".gitignore"])
        repo.index.commit("Initial commit")

        return repo

    def git_commit(
        self,
        message: str,
        files: Optional[List[str]] = None
    ) -> None:
        """
        Commit changes to git.

        Args:
            message: Commit message
            files: Optional list of files to commit (relative paths)

        Raises:
            ValueError: If no workspace loaded or not a git repo
        """
        if not self.current_workspace:
            raise ValueError("No workspace loaded")

        try:
            repo = git.Repo(self.current_workspace.path)

            if files:
                repo.index.add(files)
            else:
                # Add all changes
                repo.git.add(A=True)

            repo.index.commit(message)

        except git.InvalidGitRepositoryError:
            raise ValueError("Workspace is not a git repository")

    def git_branch(self, branch_name: str, checkout: bool = True) -> None:
        """
        Create and optionally checkout a new git branch.

        Args:
            branch_name: Name of the branch
            checkout: Whether to checkout the branch

        Raises:
            ValueError: If no workspace loaded or not a git repo
        """
        if not self.current_workspace:
            raise ValueError("No workspace loaded")

        try:
            repo = git.Repo(self.current_workspace.path)
            new_branch = repo.create_head(branch_name)

            if checkout:
                new_branch.checkout()

        except git.InvalidGitRepositoryError:
            raise ValueError("Workspace is not a git repository")

    def git_push(
        self,
        remote: str = "origin",
        branch: Optional[str] = None
    ) -> None:
        """
        Push changes to remote repository.

        Args:
            remote: Remote name
            branch: Branch name (uses current if None)

        Raises:
            ValueError: If no workspace loaded or not a git repo
        """
        if not self.current_workspace:
            raise ValueError("No workspace loaded")

        try:
            repo = git.Repo(self.current_workspace.path)

            if not branch:
                branch = repo.active_branch.name

            repo.remotes[remote].push(branch)

        except git.InvalidGitRepositoryError:
            raise ValueError("Workspace is not a git repository")

    def _apply_template(self, workspace_path: Path, template_name: str) -> None:
        """
        Apply a project template to the workspace.

        Args:
            workspace_path: Path to workspace
            template_name: Name of template to apply
        """
        # TODO: Implement template application
        # Templates should be in core/workspace/templates/
        pass

    def get_workspace_summary(self) -> Dict:
        """
        Get summary of current workspace contents.

        Returns:
            Dictionary with workspace information

        Raises:
            ValueError: If no workspace is loaded
        """
        if not self.current_workspace:
            raise ValueError("No workspace loaded")

        files = self.list_files()
        total_size = sum(f.stat().st_size for f in files)

        try:
            repo = git.Repo(self.current_workspace.path)
            git_info = {
                "branch": repo.active_branch.name,
                "commit": repo.head.commit.hexsha[:8],
                "is_dirty": repo.is_dirty(),
            }
        except git.InvalidGitRepositoryError:
            git_info = None

        return {
            "name": self.current_workspace.name,
            "path": str(self.current_workspace.path),
            "project_type": self.current_workspace.project_type,
            "file_count": len(files),
            "total_size_bytes": total_size,
            "created_at": self.current_workspace.created_at.isoformat(),
            "git": git_info,
        }
