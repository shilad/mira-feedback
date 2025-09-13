"""Directory deanonymizer to restore original content using mappings."""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from tqdm import tqdm

from shilads_helpers.libs.config_loader import load_all_configs, get_config

# Import both deanonymizer backends
try:
    from anonLLM.deanonymizer import Deanonymizer as AnonLLMDeanonymizer
    ANONLLM_AVAILABLE = True
except ImportError:
    ANONLLM_AVAILABLE = False
    
from shilads_helpers.libs.local_anonymizer import LocalDeanonymizer

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


class DirectoryDeanonymizer:
    """Restore anonymized directories to their original content."""
    
    def __init__(self, mapping_file: str):
        """Initialize the deanonymizer with a mapping file.
        
        Args:
            mapping_file: Path to the JSON mapping file
        """
        self.mapping_file = Path(mapping_file)
        
        if not self.mapping_file.exists():
            raise ValueError(f"Mapping file not found: {mapping_file}")
            
        with open(self.mapping_file, 'r') as f:
            self.mappings = json.load(f)
            
        # Check if there's a backend indicator in mappings (for future use)
        # For now, try to use LocalDeanonymizer as it's compatible with both formats
        self.deanonymizer = LocalDeanonymizer()
        
    def deanonymize_content(self, content: str, content_mappings: Dict[str, Any]) -> str:
        """Restore original content using mappings.
        
        Args:
            content: Anonymized content
            content_mappings: Mappings for this specific content
            
        Returns:
            Original content
        """
        return self.deanonymizer.deanonymize(content, content_mappings)
        
    def get_original_path(self, anonymized_path: str) -> str:
        """Get the original file path from an anonymized path.
        
        Args:
            anonymized_path: The anonymized file path
            
        Returns:
            Original file path
        """
        # If filenames were anonymized, reverse the mapping
        file_mappings = self.mappings.get('files', {})
        
        # Create reverse mapping
        reverse_mappings = {v: k for k, v in file_mappings.items()}
        
        # Try to find original path
        if anonymized_path in reverse_mappings:
            return reverse_mappings[anonymized_path]
            
        # If not found in mappings, might be unchanged
        return anonymized_path
        
    def restore_directory(self,
                         anonymized_dir: str,
                         output_dir: str,
                         restore_filenames: bool = True) -> Dict[str, Any]:
        """Restore an anonymized directory to its original state.
        
        Args:
            anonymized_dir: Path to the anonymized directory
            output_dir: Where to write the restored files
            restore_filenames: Whether to restore original filenames
            
        Returns:
            Statistics about the restoration
        """
        anon_path = Path(anonymized_dir).resolve()
        out_path = Path(output_dir).resolve()
        
        if not anon_path.exists():
            raise ValueError(f"Anonymized directory not found: {anon_path}")
            
        # Statistics
        stats = {
            'total_files': 0,
            'restored_files': 0,
            'errors': []
        }
        
        # Get content mappings
        content_mappings = self.mappings.get('content_mappings', {})
        file_mappings = self.mappings.get('files', {})
        
        # Create reverse file mapping
        reverse_file_mappings = {v: k for k, v in file_mappings.items()}
        
        # Collect all files to process
        files_to_process = []
        for root, dirs, files in os.walk(anon_path):
            for file in files:
                file_path = Path(root) / file
                # Skip the report file
                if file == 'anonymization_report.txt':
                    continue
                files_to_process.append(file_path)
                
        stats['total_files'] = len(files_to_process)
        
        # Process files with progress bar
        with tqdm(total=len(files_to_process), desc="Restoring files") as pbar:
            for file_path in files_to_process:
                try:
                    # Get relative path from anonymized directory
                    rel_path = file_path.relative_to(anon_path)
                    rel_path_str = str(rel_path)
                    
                    # Determine original path
                    if restore_filenames and rel_path_str in reverse_file_mappings:
                        original_rel_path = Path(reverse_file_mappings[rel_path_str])
                    else:
                        # Try to find by checking all mappings
                        original_rel_path = None
                        for orig, anon in file_mappings.items():
                            if anon == rel_path_str:
                                original_rel_path = Path(orig)
                                break
                        
                        if original_rel_path is None:
                            # Assume path wasn't changed
                            original_rel_path = rel_path
                            
                    # Read anonymized content
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        anon_content = f.read()
                        
                    # Get content mappings for this file
                    # Try to find the original file key in content_mappings
                    file_content_mappings = None
                    for key in content_mappings.keys():
                        if Path(key) == original_rel_path or key == str(original_rel_path):
                            file_content_mappings = content_mappings[key]
                            break
                            
                    # Restore content
                    if file_content_mappings:
                        restored_content = self.deanonymize_content(anon_content, file_content_mappings)
                    else:
                        # No mappings found, content might not have been anonymized
                        restored_content = anon_content
                        
                    # Write restored file
                    out_file_path = out_path / original_rel_path
                    out_file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(out_file_path, 'w', encoding='utf-8') as f:
                        f.write(restored_content)
                        
                    stats['restored_files'] += 1
                    
                except Exception as e:
                    LOG.error(f"Error restoring {file_path}: {e}")
                    stats['errors'].append({
                        'file': str(file_path),
                        'error': str(e)
                    })
                    
                pbar.update(1)
                
        # Create restoration report
        report_path = out_path / 'restoration_report.txt'
        with open(report_path, 'w') as f:
            f.write("Restoration Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Total files: {stats['total_files']}\n")
            f.write(f"Restored files: {stats['restored_files']}\n")
            
            if stats['errors']:
                f.write(f"\nErrors: {len(stats['errors'])}\n")
                for error in stats['errors'][:10]:
                    f.write(f"  - {error['file']}: {error['error']}\n")
                    
        LOG.info(f"Restoration complete. Report saved to {report_path}")
        
        return stats