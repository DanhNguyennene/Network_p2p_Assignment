import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
import threading  # To handle background tasks
from Network import Network  # Assuming Network class handles everything related to torrents and peers

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Peer-to-Peer Network")
        self.root.geometry("400x400")

        # Initialize the network (which will manage torrents, peers, etc.)
        self.network = Network()

        # Set up UI elements
        self.setup_ui()

    def setup_ui(self):
        # Add Torrent section
        self.torrent_name_label = tk.Label(self.root, text="Enter Torrent Path:")
        self.torrent_name_label.pack()

        self.torrent_name_entry = tk.Entry(self.root, width=50)
        self.torrent_name_entry.pack()

        # Browse button to select one or more torrent files
        self.browse_button = tk.Button(self.root, text="Browse", command=self.browse_torrent)
        self.browse_button.pack()

        self.add_torrent_button = tk.Button(self.root, text="Add Torent", command=self.add_torrent)
        self.add_torrent_button.pack()

        # Simulate Download (will run in a separate thread)
        self.download_button = tk.Button(self.root, text="Start Download", command=self.start_download)
        self.download_button.pack()

        # List Peers section
        self.list_peers_button = tk.Button(self.root, text="List Peers", command=self.list_peers)
        self.list_peers_button.pack()

    def browse_torrent(self):
        """Open a file dialog to select one or more torrent files."""
        file_paths = filedialog.askopenfilenames(title="Select Torrent Files", filetypes=[("Torrent Files", "*.torrent")])
        if file_paths:  # If files were selected
            self.torrent_name_entry.delete(0, tk.END)  # Clear the current text in the entry
            self.torrent_name_entry.insert(0, ', '.join(file_paths))  # Set the selected file paths

    def add_torrent(self):
        torrent_paths = self.torrent_name_entry.get()  # Get the torrent file paths entered by the user
        if torrent_paths:
            torrent_paths_list = torrent_paths.split(', ')  # Convert the comma-separated string into a list
            try:
                self.network.update_torrent_and_run(torrent_paths_list)  # Delegate the torrent handling to the network
                self.torrent_name_entry.delete(0, tk.END)  # Clear the input field
                messagebox.showinfo("Success", f"Torrents {', '.join(torrent_paths_list)} added to the network.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add torrents: {str(e)}")
        else:
            messagebox.showwarning("Input Error", "Please enter or select one or more torrent file paths.")

    def start_download(self):
        torrent_paths = self.torrent_name_entry.get()
        if torrent_paths:
            torrent_paths_list = torrent_paths.split(', ')  # Convert the comma-separated string into a list
            try:
                # Start the download in a separate thread so the UI doesn't block
                download_thread = threading.Thread(target=self.download_torrents, args=(torrent_paths_list,))
                download_thread.start()
                messagebox.showinfo("Success", f"Started downloading torrents: {', '.join(torrent_paths_list)}.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start download: {str(e)}")
        else:
            messagebox.showwarning("Input Error", "Please enter or select one or more torrent file paths.")

    def download_torrents(self, torrent_paths_list):
        """Simulate downloading torrents (run in a background thread)."""
        for torrent_path in torrent_paths_list:
            try:
                self.network.download_torrent(torrent_path)  # This should be a method that handles downloading in the Network class
                print(f"Started downloading {torrent_path}")
            except Exception as e:
                print(f"Failed to download {torrent_path}: {str(e)}")

    def list_peers(self):
        peers = self.network.get_peers()  # This should return the list of peers connected to the network
        if peers:
            peers_list = "\n".join(peers)
            messagebox.showinfo("Peers in the Network", peers_list)
        else:
            messagebox.showinfo("Peers in the Network", "No peers connected.")

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
