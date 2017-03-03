from pywb.warclib.statusandheaders import StatusAndHeaders
from pywb.warclib.warcwriter import BufferWARCWriter
from pywb.warclib.recordloader import ArcWarcRecordLoader
from pywb.warclib.archiveiterator import ArchiveIterator
from pywb.warclib.bufferedreaders import DecompressingBufferedReader

from io import BytesIO
from collections import OrderedDict
import json
from six import next


# ============================================================================
class FixedTestWARCWriter(BufferWARCWriter):
    @classmethod
    def _make_warc_id(cls, id_=None):
        return '<urn:uuid:12345678-feb0-11e6-8f83-68a86d1772ce>'

    @classmethod
    def _make_warc_date(cls):
        return '2000-01-01T00:00:00Z'


# ============================================================================
WARCINFO_RECORD = '\
WARC/1.0\r\n\
WARC-Type: warcinfo\r\n\
WARC-Record-ID: <urn:uuid:12345678-feb0-11e6-8f83-68a86d1772ce>\r\n\
WARC-Filename: testfile.warc.gz\r\n\
WARC-Date: 2000-01-01T00:00:00Z\r\n\
Content-Type: application/warc-fields\r\n\
Content-Length: 86\r\n\
\r\n\
software: recorder test\r\n\
format: WARC File Format 1.0\r\n\
json-metadata: {"foo": "bar"}\r\n\
\r\n\
\r\n\
'


RESPONSE_RECORD = '\
WARC/1.0\r\n\
WARC-Type: response\r\n\
WARC-Record-ID: <urn:uuid:12345678-feb0-11e6-8f83-68a86d1772ce>\r\n\
WARC-Target-URI: http://example.com/\r\n\
WARC-Date: 2000-01-01T00:00:00Z\r\n\
WARC-Block-Digest: sha1:B6QJ6BNJ3R4B23XXMRKZKHLPGJY2VE4O\r\n\
WARC-Payload-Digest: sha1:B6QJ6BNJ3R4B23XXMRKZKHLPGJY2VE4O\r\n\
Content-Type: application/http; msgtype=response\r\n\
Content-Length: 97\r\n\
\r\n\
HTTP/1.0 200 OK\r\n\
Content-Type: text/plain; charset="UTF-8"\r\n\
Custom-Header: somevalue\r\n\
\r\n\
some\n\
text\
\r\n\
\r\n\
'


REQUEST_RECORD = '\
WARC/1.0\r\n\
WARC-Type: request\r\n\
WARC-Record-ID: <urn:uuid:12345678-feb0-11e6-8f83-68a86d1772ce>\r\n\
WARC-Target-URI: http://example.com/\r\n\
WARC-Date: 2000-01-01T00:00:00Z\r\n\
WARC-Block-Digest: sha1:3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ\r\n\
WARC-Payload-Digest: sha1:3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ\r\n\
Content-Type: application/http; msgtype=request\r\n\
Content-Length: 54\r\n\
\r\n\
GET / HTTP/1.0\r\n\
User-Agent: foo\r\n\
Host: example.com\r\n\
\r\n\
\r\n\
\r\n\
'


REVISIT_RECORD = '\
WARC/1.0\r\n\
WARC-Type: revisit\r\n\
WARC-Record-ID: <urn:uuid:12345678-feb0-11e6-8f83-68a86d1772ce>\r\n\
WARC-Target-URI: http://example.com/\r\n\
WARC-Date: 2000-01-01T00:00:00Z\r\n\
WARC-Block-Digest: sha1:B6QJ6BNJ3R4B23XXMRKZKHLPGJY2VE4O\r\n\
WARC-Payload-Digest: sha1:B6QJ6BNJ3R4B23XXMRKZKHLPGJY2VE4O\r\n\
WARC-Profile: http://netpreserve.org/warc/1.0/revisit/identical-payload-digest\r\n\
WARC-Refers-To-Target-URI: http://example.com/foo\r\n\
WARC-Refers-To-Date: 1999-01-01T00:00:00Z\r\n\
Content-Type: application/http; msgtype=response\r\n\
Content-Length: 88\r\n\
\r\n\
HTTP/1.0 200 OK\r\n\
Content-Type: text/plain; charset="UTF-8"\r\n\
Custom-Header: somevalue\r\n\
\r\n\
\r\n\
\r\n\
'


class TestWarcWriter(object):
    def _validate_record_content_len(self, stream):
        for record in ArchiveIterator(stream, no_record_parse=True):
            assert record.status_headers == None
            assert int(record.rec_headers.get_header('Content-Length')) == record.length
            assert record.length == len(record.stream.read())


    def test_warcinfo_record(self):
        simplewriter = FixedTestWARCWriter(gzip=False)
        params = OrderedDict([('software', 'recorder test'),
                              ('format', 'WARC File Format 1.0'),
                              ('invalid', ''),
                              ('json-metadata', json.dumps({'foo': 'bar'}))])

        record = simplewriter.create_warcinfo_record('testfile.warc.gz', params)
        simplewriter.write_record(record)
        buff = simplewriter.get_contents()
        assert isinstance(buff, bytes)

        buff = BytesIO(buff)
        parsed_record = ArcWarcRecordLoader().parse_record_stream(buff)

        assert parsed_record.rec_headers.get_header('WARC-Type') == 'warcinfo'
        assert parsed_record.rec_headers.get_header('Content-Type') == 'application/warc-fields'
        assert parsed_record.rec_headers.get_header('WARC-Filename') == 'testfile.warc.gz'

        buff = parsed_record.stream.read().decode('utf-8')

        length = parsed_record.rec_headers.get_header('Content-Length')

        assert len(buff) == int(length)

        assert 'json-metadata: {"foo": "bar"}\r\n' in buff
        assert 'format: WARC File Format 1.0\r\n' in buff

        assert simplewriter.get_contents().decode('utf-8') == WARCINFO_RECORD

    def _sample_response(self, writer):
        headers_list = [('Content-Type', 'text/plain; charset="UTF-8"'),
                        ('Custom-Header', 'somevalue')
                       ]

        payload = b'some\ntext'

        status_headers = StatusAndHeaders('200 OK', headers_list, protocol='HTTP/1.0')

        record = writer.create_warc_record('http://example.com/', 'response',
                                           payload=BytesIO(payload),
                                           length=len(payload),
                                           status_headers=status_headers)

        return record

    def _sample_request(self, writer):
        headers_list = [('User-Agent', 'foo'),
                        ('Host', 'example.com')]

        status_headers = StatusAndHeaders('GET / HTTP/1.0', headers_list)

        record = writer.create_warc_record('http://example.com/', 'request',
                                           status_headers=status_headers)
        return record

    def test_generate_response(self):
        writer = FixedTestWARCWriter(gzip=False)

        record = self._sample_response(writer)

        writer.write_record(record)

        buff = writer.get_contents()

        self._validate_record_content_len(BytesIO(buff))

        assert buff.decode('utf-8') == RESPONSE_RECORD

    def test_generate_response_gzip(self):
        writer = FixedTestWARCWriter(gzip=True)

        record = self._sample_response(writer)

        writer.write_record(record)

        gzip_buff = writer.get_contents()

        self._validate_record_content_len(BytesIO(gzip_buff))

        stream = writer.get_stream()
        stream = DecompressingBufferedReader(stream)

        buff = stream.read()
        assert len(buff) > len(gzip_buff)

        assert buff.decode('utf-8') == RESPONSE_RECORD

    def test_generate_request(self):
        writer = FixedTestWARCWriter(gzip=False)

        record = self._sample_request(writer)

        writer.write_record(record)

        buff = writer.get_contents()

        assert buff.decode('utf-8') == REQUEST_RECORD

    def test_request_response_concur(self):
        writer = BufferWARCWriter(gzip=False)

        resp = self._sample_response(writer)

        req = self._sample_request(writer)

        writer.write_request_response_pair(req, resp)

        stream = writer.get_stream()

        reader = ArchiveIterator(stream)
        resp, req = list(reader)

        resp_id = resp.rec_headers.get_header('WARC-Record-ID')
        req_id = req.rec_headers.get_header('WARC-Record-ID')

        assert resp_id != req_id
        assert resp_id == req.rec_headers.get_header('WARC-Concurrent-To')

    def test_conv_to_revisit(self):
        writer = FixedTestWARCWriter(gzip=False)

        record = self._sample_response(writer)

        writer.create_revisit_record(record, 'http://example.com/foo', '1999-01-01T00:00:00Z')

        writer.write_record(record)

        buff = writer.get_contents()

        assert buff.decode('utf-8') == REVISIT_RECORD

    def test_arc2warc(self):
        from pywb import get_test_dir
        test_warc_dir = get_test_dir() + 'warcs/'

        writer = FixedTestWARCWriter(gzip=False)

        with open(test_warc_dir + 'example.arc.gz', 'rb') as fh:
            for record in ArchiveIterator(fh, arc2warc=True):
                writer.write_record(record)

            buff = writer.get_contents()

        self._validate_record_content_len(BytesIO(buff))

        buff = buff.decode('utf-8')

        assert 'WARC-Filename: live-web-example.arc.gz' in buff
        assert 'Content-Type: application/warc-fields' in buff

        assert 'WARC-Target-URI: http://example.com/' in buff

