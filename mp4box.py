import struct
import json
import datetime


class Mp4File:

    def __init__(self, filename):
        self.filename = filename
        self.child_boxes = []
        with open(filename, 'rb') as f:
            end_of_file = False
            while not end_of_file:
                current_header = Header(f)
                if current_header.type == 'ftyp':
                    current_box = FtypBox(f, current_header)
                elif current_header.type == 'moov':
                    current_box = MoovBox(f, current_header)
                elif current_header.type == 'free':
                    current_box = FreeBox(f, current_header)
                else:
                    current_box = UndefinedBox(f, current_header)
                self.child_boxes.append(current_box)
                if current_box.size == 0:
                    end_of_file = True
                f.seek(current_header.size, 1)
                if len(f.read(4)) != 4:
                    end_of_file = True
                else:
                    f.seek(-4, 1)


class Mp4Box:

    def __init__(self, header):
        self.header = header
        self.start_of_box = 0
        self.child_boxes = []
        self.box_info = {}

    def get_box_data(self):
        return json.dumps(self.box_info, indent=4) if len(self.box_info) > 0 else ""

    @property
    def size(self):
        return self.header.size

    @property
    def type(self):
        return self.header.type

    def get_children(self):
        return json.dumps([box.type for box in self.child_boxes]) if len(self.child_boxes) > 0 else ""


class Mp4FullBox(Mp4Box):

    def __init__(self, header):
        super().__init__(header)

    def set_version_and_flags(self, four_bytes):
        return {'version': four_bytes // 16777216, 'flags': "{0:#08x}".format(four_bytes % 16777216)}


class Header:

    def __init__(self, fp):
        start_of_box = fp.tell()
        self._size = struct.unpack('>I', fp.read(4))[0]
        self.type = fp.read(4).decode('utf-8')
        if self.size == 1:
            self._largesize = struct.unpack('>Q', fp.read(8))[0]
        if self.type == 'uuid':
            self.uuid = fp.read(16)
        self.header_size = fp.tell() - start_of_box
        fp.seek(start_of_box)

    @property
    def size(self):
        if self._size == 1:
            return self._largesize
        else:
            return self._size

    def get_header(self):
        ret_header = {"size": self._size, "type": self.type}
        if self.size == 1:
            ret_header['largesize'] = self._largesize
        if self.type == 'uuid':
            ret_header['uuid'] = self.uuid
        return json.dumps(ret_header, indent=4)


class UndefinedBox(Mp4Box):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()


FreeBox = UndefinedBox
SkipBox = UndefinedBox


class FtypBox(Mp4Box):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        self.box_info = {'major_brand': fp.read(4).decode('utf-8'),
                         'minor_version': "".join([str(int(b)).zfill(2) for b in fp.read(4)]),
                         'compatible_brands': []}
        bytes_left = self.size - (self.header.header_size + 8)
        while bytes_left > 0:
            self.box_info['compatible_brands'].append(fp.read(4).decode('utf-8'))
            bytes_left -= 4
        fp.seek(self.start_of_box)


class MoovBox(Mp4Box):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        bytes_left = self.size - self.header.header_size
        while bytes_left > 0:
            saved_file_position = fp.tell()
            current_header = Header(fp)
            if current_header.type == 'mvhd':
                current_box = MvhdBox(fp, Header(fp))
            elif current_header.type == 'trak':
                current_box = TrakBox(fp, Header(fp))
            elif current_header.type == 'udta':
                current_box = UdtaBox(fp, Header(fp))
            else:
                current_box = UndefinedBox(fp, Header(fp))
            fp.seek(saved_file_position + current_box.size)
            self.child_boxes.append(current_box)
            bytes_left -= current_box.size
        fp.seek(self.start_of_box)


class MvhdBox(Mp4FullBox):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        self.box_info = self.set_version_and_flags(struct.unpack('>I', fp.read(4))[0])
        dt_base = datetime.datetime(1904, 1, 1, 0, 0, 0)
        if self.box_info['version'] == 1:
            self.box_info['creation_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>Q', fp.read(8))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['modification_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>Q', fp.read(8))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['timescale'] = struct.unpack('>I', fp.read(4))[0]
            self.box_info['duration'] = struct.unpack('>I', fp.read(8))[0]
        else:
            self.box_info['creation_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>I', fp.read(4))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['modification_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>I', fp.read(4))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['timescale'] = struct.unpack('>I', fp.read(4))[0]
            self.box_info['duration'] = struct.unpack('>I', fp.read(4))[0]
        self.box_info['rate'] = hex(struct.unpack('>I', fp.read(4))[0])
        self.box_info['volume'] = hex(struct.unpack('>H', fp.read(2))[0])
        fp.seek(10, 1)
        self.box_info['matrix'] = [hex(int(b)) for b in struct.unpack('>9I', fp.read(36))]
        fp.seek(24, 1)
        self.box_info['next_track_id'] = struct.unpack('>I', fp.read(4))[0]
        fp.seek(self.start_of_box)


class TrakBox(Mp4Box):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        bytes_left = self.size - self.header.header_size
        while bytes_left > 0:
            saved_file_position = fp.tell()
            current_header = Header(fp)
            if current_header.type == 'tkhd':
                current_box = TkhdBox(fp, Header(fp))
            elif current_header.type == 'mdia':
                current_box = MdiaBox(fp, Header(fp))
            else:
                current_box = UndefinedBox(fp, Header(fp))
            fp.seek(saved_file_position + current_box.size)
            self.child_boxes.append(current_box)
            bytes_left -= current_box.size
        fp.seek(self.start_of_box)


class TkhdBox(Mp4FullBox):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        self.box_info = self.set_version_and_flags(struct.unpack('>I', fp.read(4))[0])
        dt_base = datetime.datetime(1904, 1, 1, 0, 0, 0)
        if self.box_info['version'] == 1:
            self.box_info['creation_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>Q', fp.read(8))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['modification_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>Q', fp.read(8))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['track_ID'] = struct.unpack('>I', fp.read(4))[0]
            fp.seek(4, 1)
            self.box_info['duration'] = struct.unpack('>I', fp.read(8))[0]
        else:
            self.box_info['creation_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>I', fp.read(4))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['modification_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>I', fp.read(4))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['track_ID'] = struct.unpack('>I', fp.read(4))[0]
            fp.seek(4, 1)
            self.box_info['duration'] = struct.unpack('>I', fp.read(4))[0]
        fp.seek(8, 1)
        self.box_info['layer'] = hex(struct.unpack('>H', fp.read(2))[0])
        self.box_info['alternate_group'] = hex(struct.unpack('>H', fp.read(2))[0])
        self.box_info['volume'] = hex(struct.unpack('>H', fp.read(2))[0])
        fp.seek(2, 1)
        self.box_info['matrix'] = [hex(int(b)) for b in struct.unpack('>9I', fp.read(36))]
        fp.seek(24, 1)
        self.box_info['width'] = struct.unpack('>I', fp.read(4))[0]
        self.box_info['height'] = struct.unpack('>I', fp.read(4))[0]
        fp.seek(self.start_of_box)


class MdiaBox(Mp4Box):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        bytes_left = self.size - self.header.header_size
        while bytes_left > 0:
            saved_file_position = fp.tell()
            current_header = Header(fp)
            if current_header.type == 'mdhd':
                current_box = MdhdBox(fp, Header(fp))
            elif current_header.type == 'hdlr':
                current_box = HdlrBox(fp, Header(fp))
            elif current_header.type == 'minf':
                current_box = MinfBox(fp, Header(fp))
            else:
                current_box = UndefinedBox(fp, Header(fp))
            fp.seek(saved_file_position + current_box.size)
            self.child_boxes.append(current_box)
            bytes_left -= current_box.size
        fp.seek(self.start_of_box)


class MdhdBox(Mp4FullBox):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        self.box_info = self.set_version_and_flags(struct.unpack('>I', fp.read(4))[0])
        dt_base = datetime.datetime(1904, 1, 1, 0, 0, 0)
        if self.box_info['version'] == 1:
            self.box_info['creation_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>Q', fp.read(8))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['modification_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>Q', fp.read(8))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['timescale'] = struct.unpack('>I', fp.read(4))[0]
            fp.seek(4, 1)
            self.box_info['duration'] = struct.unpack('>I', fp.read(8))[0]
        else:
            self.box_info['creation_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>I', fp.read(4))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['modification_time'] = (
                    dt_base + datetime.timedelta(seconds=(struct.unpack('>I', fp.read(4))[0]))).strftime(
                '%Y-%m-%d %H:%M:%S')
            self.box_info['timescale'] = struct.unpack('>I', fp.read(4))[0]
            fp.seek(4, 1)
            self.box_info['duration'] = struct.unpack('>I', fp.read(4))[0]
        self.box_info['language'] = bin(struct.unpack('>H', fp.read(2))[0])
        fp.seek(self.start_of_box)


class MinfBox(Mp4Box):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        bytes_left = self.size - self.header.header_size
        while bytes_left > 0:
            saved_file_position = fp.tell()
            current_header = Header(fp)
            # do stuff here
            if current_header.type == 'nmhd':
                current_box = MdhdBox(fp, Header(fp))
            elif current_header.type == 'vmhd':
                current_box = VmhdBox(fp, Header(fp))
            elif current_header.type == 'smhd':
                current_box = SmhdBox(fp, Header(fp))
            elif current_header.type == 'stbl':
                current_box = StblBox(fp, Header(fp))
            else:
                current_box = UndefinedBox(fp, Header(fp))
            fp.seek(saved_file_position + current_box.size)
            self.child_boxes.append(current_box)
            bytes_left -= current_box.size
        fp.seek(self.start_of_box)


class HdlrBox(Mp4FullBox):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        self.box_info = self.set_version_and_flags(struct.unpack('>I', fp.read(4))[0])
        fp.seek(4, 1)
        self.box_info['handler_type'] = fp.read(4).decode('utf-8')
        fp.seek(12, 1)
        bytes_left = self.size - (self.header.header_size + 25)  # string is null terminated
        self.box_info['name'] = fp.read(bytes_left).decode('utf-8', errors="ignore")
        fp.seek(self.start_of_box)


class UdtaBox(Mp4Box):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        bytes_left = self.size - self.header.header_size
        while bytes_left > 0:
            saved_file_position = fp.tell()
            current_header = Header(fp)
            if current_header.type == 'meta':
                current_box = MetaBox(fp, Header(fp))
            else:
                current_box = UndefinedBox(fp, Header(fp))
            fp.seek(saved_file_position + current_box.size)
            self.child_boxes.append(current_box)
            bytes_left -= current_box.size
        fp.seek(self.start_of_box)


class MetaBox(Mp4FullBox):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        self.box_info = self.set_version_and_flags(struct.unpack('>I', fp.read(4))[0])
        bytes_left = self.size - (self.header.header_size + 4)
        while bytes_left > 0:
            saved_file_position = fp.tell()
            current_header = Header(fp)
            if current_header.type == 'hdlr':
                current_box = HdlrBox(fp, Header(fp))
            else:
                current_box = UndefinedBox(fp, Header(fp))
            fp.seek(saved_file_position + current_box.size)
            self.child_boxes.append(current_box)
            bytes_left -= current_box.size
        fp.seek(self.start_of_box)


class StblBox(Mp4Box):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        bytes_left = self.size - self.header.header_size
        while bytes_left > 0:
            saved_file_position = fp.tell()
            current_header = Header(fp)
            # if current_header.type == 'mdhd':
            #    current_box = MdhdBox(fp, Header(fp))
            # elif current_header.type == 'hdlr':
            #    current_box = HdlrBox(fp, Header(fp))
            # elif current_header.type == 'minf':
            #    current_box = MinfBox(fp, Header(fp))
            # else:
            current_box = UndefinedBox(fp, Header(fp))
            fp.seek(saved_file_position + current_box.size)
            self.child_boxes.append(current_box)
            bytes_left -= current_box.size
        fp.seek(self.start_of_box)


class VmhdBox(Mp4FullBox):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        self.box_info = self.set_version_and_flags(struct.unpack('>I', fp.read(4))[0])
        self.box_info['graphicsmode'] = bin(struct.unpack('>H', fp.read(2))[0])
        self.box_info['opcolor'] = "".join([str(format(b, 'x')).zfill(2) for b in struct.unpack('>3B', fp.read(3))])
        fp.seek(self.start_of_box)


class SmhdBox(Mp4FullBox):

    def __init__(self, fp, header):
        super().__init__(header)
        self.start_of_box = fp.tell()
        fp.seek(self.header.header_size, 1)
        self.box_info = self.set_version_and_flags(struct.unpack('>I', fp.read(4))[0])
        self.box_info['balance'] = bin(struct.unpack('>H', fp.read(2))[0])
        fp.seek(self.start_of_box)
