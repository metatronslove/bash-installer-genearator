# Check for python3
command -v python3 >/dev/null 2>&1 || { echo -e "\033[0;31mError: python3 is required but not found\033[0m"; exit 1; }
# Check for pip
command -v pip3 >/dev/null 2>&1 || { echo -e "\033[0;31mError: pip3 is required but not found\033[0m"; exit 1; }
# Install prompt_toolkit
pip3 install prompt_toolkit --user >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "\033[0;32mSuccessfully installed prompt_toolkit\033[0m"
else
    echo -e "\033[0;31mFailed to install prompt_toolkit\033[0m"
    exit 1
fi
# Ensure big is executable
chmod +x /usr/local/bin/big 2>/dev/null
