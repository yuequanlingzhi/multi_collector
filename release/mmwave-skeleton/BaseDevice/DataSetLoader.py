import numpy as np
from pathlib import Path
from typing import List, Dict, Union, Any, Tuple, Optional

class DatasetLoader:
    """
    Dataset loader for hierarchical dataset structure.
    
    Directory structure: root/subject/state/device/*.npz
    Supports accessing data using indices, slices, or name aliases.
    """
    
    def __init__(self, root_dir: Union[str, Path]) -> None:
        """
        Initialize DatasetLoader.
        
        Args:
            root_dir: Root directory path containing subject directories
        
        Raises:
            ValueError: If root directory does not exist or is not a directory
        """
        self.root = Path(root_dir)
        if not self.root.is_dir():
            raise ValueError(f"Root directory {root_dir} does not exist or is not a directory.")
        
        self._structure: List[List[List[List[Path]]]] = []
        self._subject_names: List[str] = []
        self._subject_dir_paths: List[Path] = []
        self._max_states: int = 0
        self._max_devices: int = 0
        self._max_files: int = 0
        
        # Public mappings for name aliases
        self.device_name_map: Dict[str, str] = {
            "mmwave": "milliwave",
            "mm": "milliwave",
            "rgb": "Logitech StreamCam",
        }
        self.state_name_map: Dict[str, str] = {
            "0": "静坐",
        }
        
        self._build_structure()

    def _build_structure(self) -> None:
        """Build hierarchical structure from directory tree."""
        subject_dirs = sorted([d for d in self.root.iterdir() if d.is_dir()], key=lambda x: x.name)
        
        for subj_dir in subject_dirs:
            self._subject_names.append(subj_dir.name)
            self._subject_dir_paths.append(subj_dir)
            states = []
            state_dirs = sorted([d for d in subj_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
            self._max_states = max(self._max_states, len(state_dirs))
            
            for state_dir in state_dirs:
                devices = []
                device_dirs = sorted([d for d in state_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
                self._max_devices = max(self._max_devices, len(device_dirs))
                
                for device_dir in device_dirs:
                    npz_files = sorted(
                        [f for f in device_dir.iterdir() if f.suffix == '.npz'],
                        key=lambda x: x.name
                    )
                    self._max_files = max(self._max_files, len(npz_files))
                    devices.append(npz_files)
                states.append(devices)
            self._structure.append(states)

        self._shape = (
            len(self._structure),
            self._max_states,
            self._max_devices,
            self._max_files
        )

    @property
    def shape(self) -> Tuple[int, int, int, int]:
        """
        Get dataset shape.
        
        Returns:
            Tuple of (num_subjects, max_states, max_devices, max_files)
        """
        return self._shape

    def get_mapping(
        self, 
        subject: Optional[int] = None, 
        state: Optional[Union[int, str]] = None, 
        device: Optional[Union[int, str]] = None
    ) -> Dict[int, str]:
        """
        Get index-to-name mapping for specified hierarchy level.
        
        Args:
            subject: Subject index. If None, returns all subject names mapping.
            state: State index or name/alias. If provided, returns device mapping.
            device: Device index or name/alias. If provided, returns file mapping.
        
        Returns:
            Dictionary mapping index to name: {0: "name1", 1: "name2", ...}
        
        Examples:
            >>> loader.get_mapping()  # All subject names
            >>> loader.get_mapping(0)  # States for subject 0
            >>> loader.get_mapping(0, "start")  # Devices for subject 0, state "start"
            >>> loader.get_mapping(0, 1, "uwb")  # Files for subject 0, state 1, device "uwb"
        
        Raises:
            IndexError: If index is out of range
            ValueError: If name/alias not found
        """
        if subject is None:
            return {idx: name for idx, name in enumerate(self._subject_names)}
        
        if subject < 0 or subject >= len(self._subject_dir_paths):
            raise IndexError(f"Subject index {subject} out of range [0, {len(self._subject_dir_paths)-1}]")
        
        subject_dir = self._subject_dir_paths[subject]
        
        if state is None:
            state_dirs = sorted([d for d in subject_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
            return {idx: state_dir.name for idx, state_dir in enumerate(state_dirs)}
        
        state_idx = self._resolve_state_index(state, subject) if isinstance(state, str) else state
        state_dirs = sorted([d for d in subject_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
        if state_idx < 0 or state_idx >= len(state_dirs):
            raise IndexError(f"State index {state_idx} out of range [0, {len(state_dirs)-1}]")
        
        state_dir = state_dirs[state_idx]
        
        if device is None:
            device_dirs = sorted([d for d in state_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
            return {idx: device_dir.name for idx, device_dir in enumerate(device_dirs)}
        
        device_idx = self._resolve_device_index(device, subject, state_idx) if isinstance(device, str) else device
        device_dirs = sorted([d for d in state_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
        if device_idx < 0 or device_idx >= len(device_dirs):
            raise IndexError(f"Device index {device_idx} out of range [0, {len(device_dirs)-1}]")
        
        device_dir = device_dirs[device_idx]
        npz_files = sorted([f for f in device_dir.iterdir() if f.suffix == '.npz'], key=lambda x: x.name)
        return {idx: npz_file.stem for idx, npz_file in enumerate(npz_files)}

    def __getitem__(self, key: Tuple[Any, Any, Any, Any]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Access dataset items using tuple indexing.
        
        Supports:
            - Integer indices: (0, 0, 0, 0)
            - Slices: (0, :, :, 0)
            - Name aliases for state/device: (0, "start", "uwb", 0)
        
        Args:
            key: 4-element tuple (subject, state, device, file)
        
        Returns:
            Single dict if all indices are single values, list of dicts otherwise
        
        Raises:
            IndexError: If index format is invalid or out of range
            ValueError: If name/alias not found
        """
        if not isinstance(key, tuple):
            raise IndexError("Index must be a 4-element tuple")
        if len(key) != 4:
            raise IndexError("Expected 4 indices: (subject, state, device, file)")
        
        i, j, k, l = key
        is_state_name = isinstance(j, str)
        is_device_name = isinstance(k, str)
        
        i_indices = self._normalize_index(i, len(self._structure))
        if not isinstance(i_indices, list):
            i_indices = [i_indices]
        
        result: List[Dict[str, Any]] = []
        for i_idx in i_indices:
            subject = self._structure[i_idx]
            
            if is_state_name:
                state_idx = self._resolve_state_index(j, i_idx)
                j_indices = [state_idx]
            else:
                j_indices = self._normalize_index(j, len(subject))
                if not isinstance(j_indices, list):
                    j_indices = [j_indices]
            
            for j_idx in j_indices:
                state = subject[j_idx]
                
                if is_device_name:
                    device_idx = self._resolve_device_index(k, i_idx, j_idx)
                    k_indices = [device_idx]
                else:
                    k_indices = self._normalize_index(k, len(state))
                    if not isinstance(k_indices, list):
                        k_indices = [k_indices]
                
                for k_idx in k_indices:
                    device = state[k_idx]
                    l_indices = self._normalize_index(l, len(device))
                    if not isinstance(l_indices, list):
                        l_indices = [l_indices]
                    
                    for l_idx in l_indices:
                        file_path = device[l_idx]
                        result.append(self._load_npz_to_dict(file_path))
        
        if (isinstance(i, int) and isinstance(l, int) and 
            (isinstance(j, int) or is_state_name) and
            (isinstance(k, int) or is_device_name)):
            return result[0] if result else None
        
        return result

    def __repr__(self) -> str:
        """String representation of DatasetLoader."""
        return f"DatasetLoader(root='{self.root}', shape={self.shape})"

    # Private methods
    
    def _load_npz_to_dict(self, file_path: Path) -> Dict[str, Any]:
        """
        Load .npz file and convert to dictionary.
        
        Args:
            file_path: Path to .npz file
        
        Returns:
            Dictionary containing all arrays from the .npz file
        """
        npz_file = np.load(file_path, allow_pickle=True)
        return {key: npz_file[key] for key in npz_file.keys()}

    def _normalize_index(self, idx: Union[int, slice], length: int) -> Union[int, List[int]]:
        """
        Normalize index or slice to actual indices.
        
        Args:
            idx: Integer index or slice object
            length: Length of the dimension
        
        Returns:
            Integer index or list of indices
        
        Raises:
            IndexError: If index is out of range
            TypeError: If index is not int or slice
        """
        if isinstance(idx, int):
            if idx < 0:
                idx = length + idx
            if idx < 0 or idx >= length:
                raise IndexError(f"Index {idx} out of range [0, {length-1}]")
            return idx
        elif isinstance(idx, slice):
            return list(range(*idx.indices(length)))
        else:
            raise TypeError(f"Index must be int or slice, got {type(idx)}")

    def _resolve_state_index(self, state_name: str, subject: int) -> int:
        """
        Resolve state name or alias to state index.
        
        Args:
            state_name: State name or alias from state_name_map
            subject: Subject index
        
        Returns:
            State index
        
        Raises:
            IndexError: If subject index is out of range
            ValueError: If state name not found
        """
        if subject < 0 or subject >= len(self._subject_dir_paths):
            raise IndexError(f"Subject index {subject} out of range [0, {len(self._subject_dir_paths)-1}]")
        
        subject_dir = self._subject_dir_paths[subject]
        state_dirs = sorted([d for d in subject_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
        full_state_name = self.state_name_map.get(state_name, state_name)
        
        for idx, state_dir in enumerate(state_dirs):
            if state_dir.name == full_state_name or state_dir.name == state_name:
                return idx
        
        raise ValueError(f"State '{state_name}' not found in subject {subject}. "
                        f"Available states: {[d.name for d in state_dirs]}")

    def _resolve_device_index(self, device_name: str, subject: int, state: int) -> int:
        """
        Resolve device name or alias to device index.
        
        Args:
            device_name: Device name or alias from device_name_map
            subject: Subject index
            state: State index
        
        Returns:
            Device index
        
        Raises:
            IndexError: If subject or state index is out of range
            ValueError: If device name not found
        """
        if subject < 0 or subject >= len(self._subject_dir_paths):
            raise IndexError(f"Subject index {subject} out of range [0, {len(self._subject_dir_paths)-1}]")
        
        subject_dir = self._subject_dir_paths[subject]
        state_dirs = sorted([d for d in subject_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
        if state < 0 or state >= len(state_dirs):
            raise IndexError(f"State index {state} out of range [0, {len(state_dirs)-1}]")
        
        state_dir = state_dirs[state]
        device_dirs = sorted([d for d in state_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
        full_device_name = self.device_name_map.get(device_name, device_name)
        
        for idx, device_dir in enumerate(device_dirs):
            if device_dir.name == full_device_name or device_dir.name == device_name:
                return idx
        
        raise ValueError(f"Device '{device_name}' not found in subject {subject}, state {state}. "
                        f"Available devices: {[d.name for d in device_dirs]}")


