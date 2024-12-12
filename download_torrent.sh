#!/bin/bash
sudo apt-get install dos2unix  # On Debian/Ubuntu; use your distribution's package manager
dos2unix download_torrent.sh
if [ -z "$1" ]; then
    echo "Usage: $0 <URL_of_directory>"
    exit 1
fi

URL_of_directory="$1"

curl "$URL_of_directory" | grep -Eo '<a href="[^\"]+">' | cut -d '"' -f 2 | while read file; do
    if curl -O "$URL_of_directory/$file" 2>/dev/null; then  # Suppress curl output unless there's an error
        echo "Downloaded: $file"
    else
        echo "Error downloading: $file"
    fi
done
