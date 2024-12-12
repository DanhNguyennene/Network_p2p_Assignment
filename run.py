from lib import *
from utils import *
from torrent import Torrent
from peer import Peer
from Network import Network


if __name__ == "__main__":
    # Number of peer in the network
    # The peer peer_info can be specified by users are generated automatically
    # peer_infos = generate_peer_info(num_peer)
    # tracker_info = generate_tracker_info()

    network = Network()
    # network.updata_torrent(["./TO_BE_SHARED/TO_BE_SHARED.torrent","/TO_BE_SHARED copy/TO_BE_SHARED copy.torrent","/TO_BE_SHARED copy 2/TO_BE_SHARED copy 2.torrent"])
    # network.update_torrent_and_run(["./torrents/TO_BE_SHARED.torrent"])
    network.update_torrent_and_run(["./torrents/TO_BE_SHARED.torrent","./torrents/TO_BE_SHARED_copy.torrent","./torrents/TO_BE_SHARED_copy_2.torrent"])



