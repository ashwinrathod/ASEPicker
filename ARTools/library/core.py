# ARTools/anim/library/core.py
import os
import json
import shutil
import time
import datetime
import re
from maya import cmds

class LibraryCore:
    def __init__(self, root_path=None):
        self.data_root = root_path
        self.cache_data = None
        self._init_cache_paths()

    def _init_cache_paths(self):
        if not self.data_root:
            self.cache_file = None
            return
            
        import hashlib
        import os
        
        safe_hash = hashlib.md5(self.data_root.encode('utf-8')).hexdigest()[:8]
        lib_name = os.path.basename(os.path.normpath(self.data_root))
        
        # Safely step up 2 folders from core.py (core.py -> library -> ARTools)
        module_dir = os.path.dirname(os.path.abspath(__file__))
        artools_dir = os.path.dirname(module_dir)
        parent_dir = os.path.dirname(artools_dir)
        
        # Target the ARTools_Data folder alongside the ARTools folder
        cache_dir = os.path.join(parent_dir, "ARTools_Data", "Library_Cache")
        
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir)
            except:
                pass
                
        self.cache_file = os.path.join(cache_dir, f"{lib_name}_{safe_hash}_cache.art")

    def _sanitize_name(self, name):
        return "".join([c for c in str(name or "") if c.isalnum() or c in (' ', '_', '-')]).strip()

    def _is_version_name(self, name):
        return bool(re.match(r"^V\d+$", str(name or ""), re.IGNORECASE))

    def _version_number(self, name):
        match = re.match(r"^V(\d+)$", str(name or ""), re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def _has_item_files(self, path):
        return os.path.exists(os.path.join(path, "anim.json")) and os.path.exists(os.path.join(path, "meta.json"))

    def _has_version_children(self, path):
        if not os.path.isdir(path):
            return False
        for d in os.listdir(path):
            full = os.path.join(path, d)
            if os.path.isdir(full) and self._is_version_name(d) and self._has_item_files(full):
                return True
        return False

    def get_cached_library(self, force_rebuild=False):
        if not self.cache_file: return {}
        
        if not force_rebuild and os.path.exists(self.cache_file):
            try:
                import pickle
                with open(self.cache_file, 'rb') as f:
                    self.cache_data = pickle.load(f)
                    return self.cache_data
            except Exception: pass
        
        return self.rebuild_cache()

    def rebuild_cache(self):
        if not self.data_root or not self.cache_file: return {}
        self.cache_data = {}
        
        for root, dirs, files in os.walk(self.data_root):
            dirs[:] = [d for d in dirs if d not in ("preview_sequence", "__pycache__")]
            version_dirs = [d for d in dirs if self._is_version_name(d) and os.path.exists(os.path.join(root, d, "anim.json"))]
            if "anim.json" in files or version_dirs:
                full_rel = os.path.relpath(root, self.data_root)
                if full_rel == ".": full_rel = ""
                
                name = os.path.basename(root)
                cat_path = os.path.dirname(full_rel).replace("\\", "/")
                if cat_path == ".": cat_path = ""
                
                item_id = os.path.join(cat_path, name).replace("\\", "/").strip("/")
                
                versions = self.list_item_versions(cat_path, name)
                current_version = versions[-1] if versions else "V1"
                meta = self.load_item_meta(cat_path, name, version=current_version)
                
                self.cache_data[item_id] = {
                    "name": name,
                    "rel_path": cat_path,
                    "versions": versions,
                    "current_version": current_version,
                    "meta": meta
                }
                
                # Stop walking down version folders
                dirs[:] = [d for d in dirs if not self._is_version_name(d)]
                
        self._save_cache()
        return self.cache_data

    def _save_cache(self):
        if self.cache_file and self.cache_data is not None:
            try:
                import pickle
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(self.cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            except Exception: pass

    def _update_cache_item(self, rel_path, name):
        if self.cache_data is None: return
        item_id = os.path.join(rel_path, name).replace("\\", "/").strip("/")
        versions = self.list_item_versions(rel_path, name)
        if not versions:
            self.cache_data.pop(item_id, None)
        else:
            current_version = versions[-1]
            meta = self.load_item_meta(rel_path, name, version=current_version)
            self.cache_data[item_id] = {
                "name": name, "rel_path": rel_path, "versions": versions,
                "current_version": current_version, "meta": meta
            }
        self._save_cache()

    def _remove_cache_item(self, rel_path, name):
        if self.cache_data is None: return
        item_id = os.path.join(rel_path, name).replace("\\", "/").strip("/")
        if item_id in self.cache_data:
            del self.cache_data[item_id]
            self._save_cache()

    def _remove_cache_folder(self, rel_path):
        if self.cache_data is None: return
        prefix = rel_path.replace("\\", "/").strip("/") + "/"
        keys_to_delete = [k for k in self.cache_data.keys() if k.startswith(prefix) or k == rel_path.replace("\\", "/").strip("/")]
        if keys_to_delete:
            for k in keys_to_delete: del self.cache_data[k]
            self._save_cache()
    
    def get_item_container_path(self, relative_path, item_name):
        if not self.data_root:
            return ""
        safe_name = self._sanitize_name(item_name)
        if relative_path:
            return os.path.join(self.data_root, relative_path, safe_name)
        return os.path.join(self.data_root, safe_name)

    def list_item_versions(self, relative_path, item_name):
        container = self.get_item_container_path(relative_path, item_name)
        if not container or not os.path.exists(container):
            return []

        versions = []
        if self._has_item_files(container):
            versions.append("V1")

        for d in os.listdir(container):
            full = os.path.join(container, d)
            if os.path.isdir(full) and self._is_version_name(d) and self._has_item_files(full):
                versions.append(f"V{self._version_number(d)}")

        versions = sorted(set(versions), key=self._version_number)
        return versions

    def latest_item_version(self, relative_path, item_name):
        versions = self.list_item_versions(relative_path, item_name)
        return versions[-1] if versions else "V1"

    def _migrate_legacy_item(self, relative_path, item_name):
        container = self.get_item_container_path(relative_path, item_name)
        if not container or not os.path.exists(container) or not self._has_item_files(container):
            return container

        version_dir = os.path.join(container, "V1")
        if not os.path.exists(version_dir):
            os.makedirs(version_dir)

        for entry in os.listdir(container):
            if entry == "V1":
                continue
            source = os.path.join(container, entry)
            if entry in ("anim.json", "meta.json", "thumbnail.jpg", "preview_sequence") or entry.startswith("preview."):
                shutil.move(source, os.path.join(version_dir, entry))

        return version_dir

    def get_global_tags(self):
        tag_file = os.path.join(self.data_root, "tags.json")
        if os.path.exists(tag_file):
            with open(tag_file, 'r') as f:
                return json.load(f)
        return {}

    def update_global_tags(self, rel_path, tags):
        current_tags = self.get_global_tags()
        current_tags[rel_path] = tags
        tag_file = os.path.join(self.data_root, "tags.json")
        with open(tag_file, 'w') as f:
            json.dump(current_tags, f, indent=4)

    def get_structure(self):
        # Safety check: If no root, return empty
        if not self.data_root or not os.path.exists(self.data_root):
            return {}
            
        def _scan(start_path):
            tree = {}
            if not os.path.isdir(start_path) or not os.access(start_path, os.R_OK): return tree
            items = sorted(os.listdir(start_path))

            for d in items:
                full_path = os.path.join(start_path, d)
                if os.path.isdir(full_path):
                    if self._has_item_files(full_path) or self._has_version_children(full_path):
                        continue
                    tree[d] = _scan(full_path)
            return tree
        return _scan(self.data_root)

    def get_items_in_path(self, relative_path):
        if not self.data_root: return []
        target_root = os.path.join(self.data_root, relative_path) if relative_path else self.data_root
        if not os.path.exists(target_root): return []
        
        found_items = []
        for d in os.listdir(target_root):
            full = os.path.join(target_root, d)
            if os.path.isdir(full) and (self._has_item_files(full) or self._has_version_children(full)):
                found_items.append(d)
        return sorted(found_items)

    def get_item_path(self, relative_path, item_name, version=None):
        container = self.get_item_container_path(relative_path, item_name)
        if not container:
            return ""

        if self._has_item_files(container) and not self._has_version_children(container):
            if version in (None, "", "V1"):
                return container

        target_version = version or self.latest_item_version(relative_path, item_name)
        return os.path.join(container, target_version)

    def load_item_data(self, relative_path, item_name, version=None):
        path = self.get_item_path(relative_path, item_name, version=version)
        if not path: return None, None
        
        anim_path = os.path.join(path, "anim.json")
        meta_path = os.path.join(path, "meta.json")
        
        if not os.path.exists(anim_path) or not os.path.exists(meta_path):
            return None, None
            
        try:
            with open(anim_path, 'r') as f: anim_data = json.load(f)
            with open(meta_path, 'r') as f: metadata = json.load(f)
            metadata["version"] = version or os.path.basename(path) if self._is_version_name(os.path.basename(path)) else "V1"
            return anim_data, metadata
        except Exception as e:
            print(f"Load Error {path}: {e}")
            return None, None

    def load_item_meta(self, relative_path, item_name, version=None):
        path = self.get_item_path(relative_path, item_name, version=version)
        if not path: return {}

        meta_path = os.path.join(path, "meta.json")
        if not os.path.exists(meta_path): return {}

        with open(meta_path, 'r') as f: metadata = json.load(f)
        base = os.path.basename(path)
        metadata["version"] = version or base if self._is_version_name(base) else "V1"
        return metadata if isinstance(metadata, dict) else {}
    def save_item(self, name, relative_path, anim_data, metadata, thumb_source=None, preview_source=None, version_mode="replace", version=None):
        if not self.data_root: return None
        safe_name = self._sanitize_name(name)
        if not safe_name:
            return None

        container_path = self.get_item_container_path(relative_path, safe_name)
        if not os.path.exists(container_path):
            os.makedirs(container_path)

        existing_versions = self.list_item_versions(relative_path, safe_name)
        if self._has_item_files(container_path) and not self._has_version_children(container_path):
            self._migrate_legacy_item(relative_path, safe_name)
            existing_versions = self.list_item_versions(relative_path, safe_name)

        if version_mode == "new_version":
            next_num = self._version_number(existing_versions[-1]) + 1 if existing_versions else 1
            version_name = f"V{next_num}"
        else:
            version_name = version or (existing_versions[-1] if existing_versions else "V1")

        folder_path = os.path.join(container_path, version_name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        with open(os.path.join(folder_path, "anim.json"), 'w') as f: json.dump(anim_data, f, indent=4)

        metadata["created_at"] = time.time()
        metadata["created_date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata["author"] = os.getenv('USERNAME') or os.getenv('USER') or 'Unknown'
        metadata["version"] = version_name
        metadata["version_index"] = self._version_number(version_name)
        
        with open(os.path.join(folder_path, "meta.json"), 'w') as f: json.dump(metadata, f, indent=4)

        # --- CRITICAL FIX: Prevent SameFileError when overwriting versions ---
        if thumb_source and os.path.exists(thumb_source):
            dest_thumb = os.path.join(folder_path, "thumbnail.jpg")
            if os.path.normpath(os.path.abspath(thumb_source)) != os.path.normpath(os.path.abspath(dest_thumb)):
                shutil.copy2(thumb_source, dest_thumb)
        
        if preview_source and os.path.exists(preview_source):
            ext = os.path.splitext(preview_source)[1]
            dest_preview = os.path.join(folder_path, f"preview{ext}")
            if os.path.normpath(os.path.abspath(preview_source)) != os.path.normpath(os.path.abspath(dest_preview)):
                shutil.copy2(preview_source, dest_preview)

        self._update_cache_item(relative_path, safe_name)

        return folder_path

    def _rewrite_version_metadata(self, version_path, version_name):
        meta_path = os.path.join(version_path, "meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                metadata = json.load(f)
            metadata["version"] = version_name
            metadata["version_index"] = self._version_number(version_name)
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=4)

    def delete_item_version(self, relative_path, item_name, version):
        container = self.get_item_container_path(relative_path, item_name)
        if not container or not os.path.exists(container):
            return False

        versions = self.list_item_versions(relative_path, item_name)
        if version not in versions:
            return False

        if len(versions) <= 1:
            return self.delete_item(relative_path, item_name)

        version_path = self.get_item_path(relative_path, item_name, version)
        if not version_path or not os.path.exists(version_path):
            return False

        shutil.rmtree(version_path)
        removed_index = self._version_number(version)

        for version_name in sorted(self.list_item_versions(relative_path, item_name), key=self._version_number):
            version_index = self._version_number(version_name)
            if version_index > removed_index:
                source = os.path.join(container, version_name)
                target_name = f"V{version_index - 1}"
                target = os.path.join(container, target_name)
                os.rename(source, target)
                self._rewrite_version_metadata(target, target_name)

        self._update_cache_item(relative_path, item_name)

        return True

    def delete_item(self, relative_path, item_name):
        path = self.get_item_container_path(relative_path, item_name)
        if path and os.path.exists(path):
            try: 
                shutil.rmtree(path)
                self._remove_cache_item(relative_path, item_name)
                return True
            except: return False
        return False
    
    def delete_folder(self, relative_path):
        if not self.data_root: return False
        path = os.path.join(self.data_root, relative_path)
        if os.path.exists(path):
            try: 
                shutil.rmtree(path)
                self._remove_cache_folder(relative_path)
                return True
            except: return False
        return False

    def rename_item(self, relative_path, old_name, new_name):
        safe_new = self._sanitize_name(new_name)
        if not safe_new: return False
        
        path = self.get_item_container_path(relative_path, old_name)
        new_path = self.get_item_container_path(relative_path, safe_new)
        
        if path and os.path.exists(path) and not os.path.exists(new_path):
            try:
                os.rename(path, new_path)
                self._remove_cache_item(relative_path, old_name)
                self._update_cache_item(relative_path, safe_new)
                return True
            except: return False
        return False

    def rename_folder(self, relative_path, new_name):
        if not self.data_root: return False
        safe_new = "".join([c for c in new_name if c.isalnum() or c in (' ', '_', '-')]).strip()
        if not safe_new: return False
        
        old_full = os.path.join(self.data_root, relative_path)
        parent = os.path.dirname(old_full)
        new_full = os.path.join(parent, safe_new)
        
        if os.path.exists(new_full): return False
            
        try:
            os.rename(old_full, new_full)
            self.rebuild_cache()
            return True
        except: return False

    def get_selection_sets(self, relative_path):
        if not self.data_root: return {}
        path = os.path.join(self.data_root, relative_path if relative_path else "", "selection_sets.json")
        if os.path.exists(path):
            with open(path, 'r') as f: return json.load(f)
        return {}

    def save_selection_set(self, relative_path, set_name, controls):
        if not self.data_root: return False
        folder = os.path.join(self.data_root, relative_path if relative_path else "")
        if not os.path.exists(folder): os.makedirs(folder)
        path = os.path.join(folder, "selection_sets.json")
        sets = self.get_selection_sets(relative_path)
        sets[set_name] = controls
        with open(path, 'w') as f: json.dump(sets, f, indent=4)
        return True

    def delete_selection_set(self, relative_path, set_name):
        sets = self.get_selection_sets(relative_path)
        if set_name in sets:
            del sets[set_name]
            path = os.path.join(self.data_root, relative_path if relative_path else "", "selection_sets.json")
            with open(path, 'w') as f: json.dump(sets, f, indent=4)
            return True
        return False

    def rename_selection_set(self, relative_path, old_name, new_name):
        sets = self.get_selection_sets(relative_path)
        if old_name in sets and new_name not in sets:
            sets[new_name] = sets.pop(old_name)
            path = os.path.join(self.data_root, relative_path if relative_path else "", "selection_sets.json")
            with open(path, 'w') as f: json.dump(sets, f, indent=4)
            return True
        return False

    def get_resolved_sets(self, relative_path):
        local_sets = self.get_selection_sets(relative_path)
        use_inherited = local_sets.get("__use_inherited__", False)
        
        ancestor_list = []
        has_ancestor_sets = False
        
        if relative_path:
            parts = [p for p in relative_path.replace("\\", "/").split("/") if p]
            # Build from root down to immediate parent
            for i in range(len(parts)):
                parent_path = "/".join(parts[:i])
                parent_name = parts[i-1] if i > 0 else "Library Root"
                parent_sets = self.get_selection_sets(parent_path)
                valid = {k: v for k, v in parent_sets.items() if k != "__use_inherited__"}
                if valid:
                    has_ancestor_sets = True
                    if use_inherited: ancestor_list.append((parent_name, valid))
                    
        valid_local = {k: v for k, v in local_sets.items() if k != "__use_inherited__"}
        return valid_local, ancestor_list, use_inherited, has_ancestor_sets

    def set_inheritance_flag(self, relative_path, state):
        sets = self.get_selection_sets(relative_path)
        if state: sets["__use_inherited__"] = True
        elif "__use_inherited__" in sets: del sets["__use_inherited__"]
            
        folder = os.path.join(self.data_root, relative_path if relative_path else "")
        if not os.path.exists(folder): os.makedirs(folder)
        path = os.path.join(folder, "selection_sets.json")
        with open(path, 'w') as f: json.dump(sets, f, indent=4)

    # =====================================================================
    # VISUAL FOLDER META ENGINE (COLORS, ICONS, PINS)
    # =====================================================================
    
    def get_folder_meta(self, relative_path):
        """Reads the _folder_meta.json file safely from the specific directory."""
        meta_file = os.path.join(self.data_root, relative_path, "_folder_meta.json")
        if os.path.exists(meta_file):
            try:
                with open(meta_file, 'r') as f: return json.load(f)
            except: pass
        return {}

    def set_folder_meta(self, relative_path, data):
        """Merges new settings into _folder_meta.json without destroying existing keys."""
        folder = os.path.join(self.data_root, relative_path)
        if not os.path.exists(folder): os.makedirs(folder)
        meta_file = os.path.join(folder, "_folder_meta.json")
        
        current = self.get_folder_meta(relative_path)
        current.update(data)
        
        try:
            with open(meta_file, 'w') as f: json.dump(current, f, indent=4)
        except Exception as e:
            cmds.warning(f"[ARTools] Could not save folder visuals: {e}")
            
    def get_global_pinned_folders(self):
        """Scans the library to find all folders marked as 'Pinned for Studio'."""
        pins = []
        if not self.data_root or not os.path.exists(self.data_root): return pins
        
        for root, dirs, files in os.walk(self.data_root):
            if "_folder_meta.json" in files:
                rel = os.path.relpath(root, self.data_root)
                if rel == ".": rel = ""
                meta = self.get_folder_meta(rel)
                if meta.get("pin_global"):
                    pins.append(rel.replace("\\", "/"))
        return pins
    
    # =====================================================================
    # DIRECTORY MANAGEMENT ENGINE
    # =====================================================================
    def create_folder(self, parent_rel, folder_name):
        """Safely creates a new directory."""
        if not self.data_root: return False
        target = os.path.join(self.data_root, parent_rel, folder_name)
        if not os.path.exists(target):
            try: 
                os.makedirs(target)
                return True
            except Exception as e:
                cmds.warning(f"[ARTools] Cannot create folder: {e}")
        return False

    def rename_folder(self, old_rel, new_name):
        """Safely renames a directory and preserves its meta."""
        if not self.data_root or not old_rel: return False
        old_path = os.path.join(self.data_root, old_rel)
        parent = os.path.dirname(old_path)
        new_path = os.path.join(parent, new_name)
        
        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                os.rename(old_path, new_path)
                return True
            except Exception as e:
                cmds.warning(f"[ARTools] Cannot rename folder: {e}")
        return False

    def delete_folder(self, rel_path):
        """Safely deletes a directory (Requires user confirmation in UI first)."""
        if not self.data_root or not rel_path: return False
        target = os.path.join(self.data_root, rel_path)
        if os.path.exists(target):
            try:
                import shutil
                shutil.rmtree(target)
                return True
            except Exception as e:
                cmds.warning(f"[ARTools] Cannot delete folder: {e}")
        return False