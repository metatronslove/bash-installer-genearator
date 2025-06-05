#!/usr/bin/env python3
import subprocess
import os
import base64
import zlib
import json
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.key_binding import KeyBindings

class InstallerTUI:
	def __init__(self):
		self.files = []  # List of (filename, path, target_path)
		self.post_install_script = ""
		self.output_file = "installer.sh"
		self.session = PromptSession(multiline=False, completer=PathCompleter())
		self.bindings = KeyBindings()

	def clear_console(self):
		"""Clear the console screen."""
		os.system('clear' if os.name != 'nt' else 'cls')

	def add_directory_recursive(self):
		self.clear_console()
		print("\nEnter directory path to scan recursively:")
		dir_path = self.session.prompt("> ")
		if not os.path.isdir(dir_path):
			print("Invalid directory path.")
			self.session.prompt("Press Enter to continue...")
			return

		# Check for post-install-instructions.sh
		post_install_path = os.path.join(dir_path, "post-install-instructions.sh")
		if os.path.isfile(post_install_path):
			try:
				with open(post_install_path, "r") as f:
					self.post_install_script = f.read().strip()
				print("Found and set post-install-instructions.sh as post-installation script.")
			except Exception as e:
				print(f"Error reading post-install-instructions.sh: {str(e)}")
				self.session.prompt("Press Enter to continue...")
				return
		else:
			print("Warning: post-install-instructions.sh not found in directory root. No post-installation script will be included.")
			self.post_install_script = ""

		# Collect files, excluding post-install-instructions.sh
		file_list = []
		try:
			for root, _, files in os.walk(dir_path):
				for filename in files:
					if filename != "post-install-instructions.sh":
						file_path = os.path.join(root, filename)
						file_list.append((filename, file_path))
		except Exception as e:
			print(f"Error scanning directory: {str(e)}")
			self.session.prompt("Press Enter to continue...")
			return

		if not file_list:
			print("No files found in directory (excluding post-install-instructions.sh).")
			self.session.prompt("Press Enter to continue...")
			return

		# Display directory tree
		self.clear_console()
		print("\nDirectory tree:")
		try:
			subprocess.run(["tree", dir_path], check=True)
		except (subprocess.CalledProcessError, FileNotFoundError):
			print("(tree command not found, using fallback listing)")
			for i, (filename, file_path) in enumerate(file_list, 1):
				print(f"{i}. {file_path}")

		# Prompt for file selection
		print("\nEnter file indices to include (e.g., '1,3-5' or 'all' for all files, 'q' to cancel):")
		selection = self.session.prompt("> ")
		if selection.lower() == 'q':
			self.session.prompt("Press Enter to continue...")
			return
		if selection.lower() == 'all':
			selected_indices = list(range(len(file_list)))
		else:
			selected_indices = []
			try:
				for part in selection.split(','):
					if '-' in part:
						start, end = map(int, part.split('-'))
						selected_indices.extend(range(start - 1, end))
					else:
						selected_indices.append(int(part) - 1)
			except ValueError:
				print("Invalid selection format.")
				self.session.prompt("Press Enter to continue...")
				return

		# Add selected files
		self.files = []  # Reset files list
		for idx in selected_indices:
			if 0 <= idx < len(file_list):
				filename, file_path = file_list[idx]
				target_path = f"/usr/local/bin/{filename}"
				self.files.append((filename, file_path, target_path))
				print(f"Added: {filename} -> {target_path}")
			else:
				print(f"Invalid index: {idx + 1}")

		if not selected_indices:
			print("No files selected.")
		self.session.prompt("Press Enter to continue...")
		self.clear_console()

	def update_target_paths(self):
		self.clear_console()
		if not self.files:
			print("No files to update.")
			self.session.prompt("Press Enter to continue...")
			return
		print("\nUpdate target paths (press Enter to keep default, 'q' to finish):")
		for i, (filename, _, target_path) in enumerate(self.files):
			print(f"\nFile: {filename}, Current target: {target_path}")
			new_path = self.session.prompt("New target path> ")
			if new_path.lower() == 'q':
				break
			if new_path:
				self.files[i] = (filename, self.files[i][1], new_path)
				print(f"Updated: {filename} -> {new_path}")
			self.session.prompt("Press Enter to continue...")
			self.clear_console()

	def set_output_file(self):
		self.clear_console()
		print("\nEnter output bash script name (default: installer.sh):")
		output = self.session.prompt("> ")
		if output:
			self.output_file = output if output.endswith(".sh") else output + ".sh"
		print(f"Output file set to: {self.output_file}")
		self.session.prompt("Press Enter to continue...")
		self.clear_console()

	def generate_script(self):
		self.clear_console()
		if not self.files:
			print("Error: No files added.")
			self.session.prompt("Press Enter to continue...")
			return

		file_data = []
		for filename, file_path, target_path in self.files:
			try:
				with open(file_path, "rb") as f:
					content = f.read()
					compressed = zlib.compress(content)
					encoded = base64.b64encode(compressed).decode("utf-8")
					file_data.append({
						"filename": filename,
						"target_path": target_path,
						"content": encoded
					})
			except Exception as e:
				print(f"Error processing {filename}: {str(e)}")
				self.session.prompt("Press Enter to continue...")
				return

		json_data = json.dumps({"files": file_data, "post_install": self.post_install_script})

		bash_script = f"""#!/bin/bash

# ANSI color codes
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

echo -e "${{YELLOW}}Starting installation...${{NC}}"

# Check for required commands
command -v base64 >/dev/null 2>&1 || {{ echo -e "${{RED}}Error: base64 command not found${{NC}}"; exit 1; }}
command -v mkdir >/dev/null 2>&1 || {{ echo -e "${{RED}}Error: mkdir command not found${{NC}}"; exit 1; }}

# JSON data
read -r -d '' JSON_DATA << 'EOF'
{json_data}
EOF

# Function to decode and decompress
install_file() {{
	local filename="$1"
	local target_path="$2"
	local content="$3"
	local target_dir=$(dirname "$target_path")
	
	echo -e "${{YELLOW}}Installing $filename to $target_path...${{NC}}"
	
	mkdir -p "$target_dir" || {{ echo -e "${{RED}}Failed to create directory $target_dir${{NC}}"; exit 1; }}
	
	echo "$content" | base64 -d | zcat > "$target_path" 2>/dev/null
	if [ $? -eq 0 ]; then
		chmod +x "$target_path" 2>/dev/null
		echo -e "${{GREEN}}Successfully installed $filename${{NC}}"
	else
		echo -e "${{RED}}Failed to install $filename${{NC}}"
		exit 1
	fi
}}

# Parse JSON and install files
while IFS= read -r file; do
	filename=$(echo "$file" | grep -o '"filename":"[^"]*"' | cut -d'"' -f4)
	target_path=$(echo "$file" | grep -o '"target_path":"[^"]*"' | cut -d'"' -f4)
	content=$(echo "$file" | grep -o '"content":"[^"]*"' | cut -d'"' -f4)
	[ -n "$filename" ] && install_file "$filename" "$target_path" "$content"
done < <(echo "$JSON_DATA" | grep -o '{{"filename":"[^"]*","target_path":"[^"]*","content":"[^"]*"}}')

# Run post-installation script
post_install=$(echo "$JSON_DATA" | grep -o '"post_install":"[^"]*"' | cut -d'"' -f4 | sed 's/\\\\n/\\n/g')
if [ -n "$post_install" ]; then
	echo -e "${{YELLOW}}Running post-installation script...${{NC}}"
	eval "$post_install" 2>/dev/null
	if [ $? -eq 0 ]; then
		echo -e "${{GREEN}}Post-installation script completed${{NC}}"
	else
		echo -e "${{RED}}Post-installation script failed${{NC}}"
		exit 1
	fi
fi

echo -e "${{GREEN}}Installation completed successfully!${{NC}}"
"""

		try:
			with open(self.output_file, "w") as f:
				f.write(bash_script)
			print(f"Success: Bash script generated as {self.output_file}")
		except Exception as e:
			print(f"Error writing script: {str(e)}")
		self.session.prompt("Press Enter to continue...")
		self.clear_console()

	def run(self):
		try:
			while True:
				self.clear_console()				
				print("\033[0;31m 888888b.  \033[0;32m8888888 \033[0;34m.d8888b.  \033[0m")
				print("\033[0;31m 888  \"88b   \033[0;32m888  \033[0;34md88P  Y88b \033[0m")
				print("\033[0;31m 888  .88P   \033[0;32m888  \033[0;34m888	888 \033[0m")
				print("\033[0;31m 8888888K.   \033[0;32m888  \033[0;34m888		\033[0m")
				print("\033[0;31m 888  \"Y88b  \033[0;32m888  \033[0;34m888  88888 \033[0m")
				print("\033[0;31m 888	888  \033[0;32m888  \033[0;34m888	888 \033[0m")
				print("\033[0;31m 888   d88P  \033[0;32m888  \033[0;34mY88b  d88P \033[0m")
				print("\033[0;31m 8888888P\" \033[0;32m8888888 \033[0;34m\"Y8888P88 \033[0m")
				print("\033[0;35m github.com/metatronslove \033[0m")
				print("┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
				print("┃ Bash Installer Generator • 2025 ┃")
				print("┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
				print(f"1. Add directory (recursive) ({len(self.files)} files)")
				print(f"2. Update target paths ({len(self.files)} files)")
				print(f"3. Set output script name ({self.output_file})")
				print(f"4. Generate bash script")
				print("5. Exit\n")
				choice = self.session.prompt("Select an option (1-5): ")
				
				if choice == '1':
					self.add_directory_recursive()
				elif choice == '2':
					self.update_target_paths()
				elif choice == '3':
					self.set_output_file()
				elif choice == '4':
					self.generate_script()
				elif choice == '5':
					print("Exiting...")
					break
				else:
					print("Invalid choice. Try again.")
					self.session.prompt("Press Enter to continue...")
					self.clear_console()
		finally:
			self.clear_console()  # Ensure console is cleared on exit

if __name__ == "__main__":
	try:
		from prompt_toolkit import PromptSession
	except ImportError:
		print("Error: prompt_toolkit is required. Install with 'pip install prompt_toolkit'.")
		exit(1)
	InstallerTUI().run()
