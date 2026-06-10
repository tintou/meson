#!/usr/bin/env python3
"""Upload built HTML docs to the documentation branch of the meson repository."""
import shutil
import subprocess
import sys
import pathlib
import tempfile


DOC_BRANCH = 'documentation'


def main() -> None:
    html_dir, source_dir = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    if not html_dir.is_dir():
        sys.exit(f'HTML directory not found: {html_dir}')

    remote_url = subprocess.run(
        ['git', '-C', str(source_dir), 'remote', 'get-url', 'origin'],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = pathlib.Path(tmpdir) / 'website'
        subprocess.run(
            ['git', 'clone', '--depth=1', '--branch', DOC_BRANCH,
             remote_url, str(repo)],
            capture_output=True,
        )
        if not repo.exists():
            # Branch does not exist yet — create an orphan
            repo.mkdir()
            subprocess.run(['git', '-C', str(repo), 'init'], check=True)
            subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin', remote_url], check=True)
            subprocess.run(['git', '-C', str(repo), 'checkout', '--orphan', DOC_BRANCH], check=True)

        # Remove all tracked content except the .git directory
        for item in repo.iterdir():
            if item.name == '.git':
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        # Copy new HTML content
        shutil.copytree(html_dir, repo, dirs_exist_ok=True)

        # Disable Jekyll processing so GitHub Pages serves _static and other
        # underscore-prefixed directories without stripping them.
        (repo / '.nojekyll').touch()

        subprocess.run(['git', '-C', str(repo), 'add', '-A'], check=True)

        result = subprocess.run(
            ['git', '-C', str(repo), 'diff', '--cached', '--quiet'],
        )
        if result.returncode == 0:
            print('No changes to upload.')
            return

        subprocess.run(
            ['git', '-C', str(repo), 'commit', '-m', 'Update website'],
            check=True,
        )
        subprocess.run(['git', '-C', str(repo), 'push', 'origin', DOC_BRANCH], check=True)

    print('Website updated successfully.')


if __name__ == '__main__':
    main()
