import socket
from bencodepy import encode
from hashlib import md5, sha1
from os import path, walk
from time import time
from urllib.parse import urlparse


class makeTorrent:
    """
    Create single or multi-file torrents
    keywords:
      announcelist: a list of lists with announceurls [['http://example.com/announce']]
      httpseeds: a list of urls ['http://1.com/file', http://2.com/file]
      comment: text comment for torrent
    Several values are generated automtically:
      name: based on filename or path
      technical info: generates when a single or multi file is added
    """
    def __init__(self, announce, piece_length=1024*512, **kw):
        self.piece_length = piece_length
        if not bool(urlparse(announce).scheme):
            raise ValueError('No schema present for url')
        self.tdict = {
            'announce': announce,
            'creation date': int(time()),
            'info': {
                'piece length': self.piece_length
            }
        }
        if kw.get('comment'):
            self.tdict.update({'comment': kw.get('comment')})
        if kw.get('httpseeds'):
            if not isinstance(kw.get('httpseeds'), list):
                raise TypeError('httpseeds must be a list')
            else:
                self.tdict.update({'httpseeds': kw.get('httpseeds')})
        if kw.get('announcelist'):
            if not isinstance(kw.get('announcelist'), list):
                raise TypeError('announcelist must be a list of lists')
            if False in [isinstance(l, list) for l in kw.get('announcelist')]:
                raise TypeError('announcelist must be a list of lists')
            if False in [bool(urlparse(f[0]).scheme) for f in kw.get('announcelist')]:
                raise ValueError('No schema present for url')
            else:
                self.tdict.update({'announce-list': kw.get('announcelist')})

    def getDict(self):
        return self.tdict

    def info_hash(self):
        return sha1(encode(self.tdict['info'])).hexdigest()

    def getBencoded(self):
        return encode(self.tdict)

    def multi_file(self, basePath, check_md5=False):
        """
        Generate multi-file torrent
          check_md5: adds md5sum to the torrentlist
          basePath: path to folder
        Torrent name will automatically be basePath
        """
        if 'length' in self.tdict['info']:
            raise TypeError('Cannot add multi-file to single-file torrent')
        if basePath.endswith('/'):
            basePath = basePath[:-1]
        realPath = path.abspath(basePath).replace('\\', '/').replace('\\\\', '/')
        toGet = []
        fileList = []
        info_pieces = b""
        data = b""
        for root, subdirs, files in walk(realPath):
            for f in files:
                subPath = path.relpath(path.join(root, f), start=realPath).replace('\\', '/').replace('\\\\', '/').split('/')
                subPath = [str(p) for p in subPath]
                toGet.append(subPath)
        for pathList in toGet:
            length = 0
            filePath = ('/').join(pathList)
            if check_md5:
                md5sum = md5()
            fileDict = {
                'path': pathList,
                'length': len(open(path.join(basePath, filePath), "rb").read())
            }
            with open(path.join(basePath, filePath), "rb") as fn:
                while True:
                    filedata = fn.read(self.piece_length)

                    if len(filedata) == 0:
                        break
                    length += len(filedata)

                    data += filedata

                    if len(data) >= self.piece_length:
                        info_pieces += sha1(data[:self.piece_length]).digest()
                        data = data[self.piece_length:]

                    if check_md5:
                        md5sum.update(filedata)
                        fileDict['md5sum'] = md5sum.hexdigest()
            fileList.append(fileDict)
        if len(data) > 0:
            info_pieces += sha1(data).digest()
        self.tdict['info'].update(
            {
                'name': str(path.basename(realPath)),
                'files': fileList,
                'pieces': info_pieces
            }
        )
        info_hash = sha1(encode(self.tdict['info'])).hexdigest()
        return {'Created': info_hash}

    def single_file(self, fileName, check_md5=False):
        """
        Creates a torrent containing one file
          fileName: file to create torrent from
          check_md5: add md5sum to torrent
        Torrent name will be filename
        """
        if 'files' in self.tdict['info']:
            raise TypeError('Cannot add single file to multi-file torrent')
        info_pieces = b''
        data = b''
        realPath = path.abspath(fileName)
        length = 0
        if check_md5:
            md5sum = md5()
        with open(realPath, "rb") as fn:
            while True:
                filedata = fn.read(self.piece_length)

                if len(filedata) == 0:
                    break

                length += len(filedata)

                data += filedata

                if len(data) >= self.piece_length:
                    info_pieces += sha1(data[:self.piece_length]).digest()
                    data = data[self.piece_length:]

                if check_md5:
                    md5sum.update(filedata)
        if len(data) > 0:
            info_pieces += sha1(data).digest()

        self.tdict['info'].update(
            {
                'length': length,
                'pieces': info_pieces,
                'name': str(path.basename(realPath)).replace('\\', '/').replace('\\\\', '/')
            }
        )
        if check_md5:
            self.tdict['info'].update(
                {
                    'md5sum': md5sum.hexdigest()
                }
            )
        info_hash = sha1(encode(self.tdict['info'])).hexdigest()
        return {'Created': info_hash}

def get_external_ip():
    """Automatically determine the external IP address of the machine."""
    try:
        # Create a dummy socket to determine the external IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Connect to a public DNS server
        ip = s.getsockname()[0]  # Get the IP of the interface used
        s.close()
        return ip
    except Exception as e:
        return "127.0.0.1"

# Create the torrent
mk = makeTorrent(announce=f"http://{get_external_ip()}:8000/")
# name = './TO_BE_SHARED copy 2'
# name = './TO_BE_SHARED copy'
#name = './TO_BE_SHARED'
name = ['./TO_BE_SHARED','./TO_BE_SHARED_copy','./TO_BE_SHARED_copy_2']
for i in name:
    mk.multi_file(i)

    # Write the encoded torrent to a file
    with open(f'./torrents/{i}.torrent', 'wb') as tf:
        tf.write(mk.getBencoded())
