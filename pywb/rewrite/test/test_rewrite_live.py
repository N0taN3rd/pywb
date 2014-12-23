from pywb.rewrite.rewrite_live import LiveRewriter
from pywb.rewrite.url_rewriter import UrlRewriter
from pywb.rewrite.wburl import WbUrl

from pywb import get_test_dir

from io import BytesIO

# This module has some rewriting tests against the 'live web'
# As such, the content may change and the test may break

urlrewriter = UrlRewriter('20131226101010/http://example.com/some/path/index.html', '/pywb/')
bn_urlrewriter = UrlRewriter('20131226101010bn_/http://example.com/some/path/index.html', '/pywb/')

def head_insert_func(rule, cdx):
    if rule.js_rewrite_location != 'urls':
        return '<script src="/static/default/wombat.js"> </script>'
    else:
        return ''

def test_csrf_token_headers():
    rewriter = LiveRewriter()
    env = {'HTTP_X_CSRFTOKEN': 'wrong', 'HTTP_COOKIE': 'csrftoken=foobar'}

    req_headers = rewriter.translate_headers('http://example.com/', env)

    assert req_headers == {'X-CSRFToken': 'foobar', 'Cookie': 'csrftoken=foobar'}

def test_local_1():
    status_headers, buff = get_rewritten(get_test_dir() + 'text_content/sample.html',
                                         urlrewriter,
                                         head_insert_func,
                                         'com,example,test)/')

    # wombat insert added
    assert '<head><script src="/static/default/wombat.js"> </script>' in buff, buff

    # JS location and JS link rewritten
    assert 'window.WB_wombat_location = "/pywb/20131226101010/http:\/\/example.com/dynamic_page.html"' in buff

    # link rewritten
    assert '"/pywb/20131226101010/http://example.com/some/path/another.html"' in buff


def test_local_no_head():
    status_headers, buff = get_rewritten(get_test_dir() + 'text_content/sample_no_head.html',
                                         urlrewriter,
                                         head_insert_func,
                                         'com,example,test)/')

    # wombat insert added
    assert '<script src="/static/default/wombat.js"> </script>' in buff

    # location rewritten
    assert 'window.WB_wombat_location = "/other.html"' in buff

    # link rewritten
    assert '"/pywb/20131226101010/http://example.com/some/path/another.html"' in buff

def test_local_no_head_banner_only():
    status_headers, buff = get_rewritten(get_test_dir() + 'text_content/sample_no_head.html',
                                         bn_urlrewriter,
                                         head_insert_func,
                                         'com,example,test)/')

    # wombat insert added
    assert '<script src="/static/default/wombat.js"> </script>' in buff

    # location NOT rewritten
    assert 'window.location = "/other.html"' in buff

    # link NOT rewritten
    assert '"another.html"' in buff

def test_local_banner_only_no_rewrite():
    status_headers, buff = get_rewritten(get_test_dir() + 'text_content/sample.html',
                                         bn_urlrewriter,
                                         head_insert_func,
                                         'com,example,test)/')

    # wombat insert added
    assert '<head><script src="/static/default/wombat.js"> </script>' in buff

    # JS location NOT rewritten, JS link NOT rewritten
    assert 'window.location = "http:\/\/example.com/dynamic_page.html"' in buff, buff

    # link NOT rewritten
    assert '"another.html"' in buff

def test_local_2_link_only_rewrite():
    status_headers, buff = get_rewritten(get_test_dir() + 'text_content/sample.html',
                                         urlrewriter,
                                         head_insert_func,
                                         'example,example,test)/nolocation_rewrite')

    # no wombat insert
    assert '<head><script src="/static/default/wombat.js"> </script>' not in buff

    # JS location NOT rewritten, JS link rewritten
    assert 'window.location = "/pywb/20131226101010/http:\/\/example.com/dynamic_page.html"' in buff

    # still link rewrite
    assert '"/pywb/20131226101010/http://example.com/some/path/another.html"' in buff


def test_local_2_js_loc_only_rewrite():
    status_headers, buff = get_rewritten(get_test_dir() + 'text_content/sample.html',
                                         urlrewriter,
                                         head_insert_func,
                                         'example,example,test,loconly)/')

    # wombat insert added
    assert '<script src="/static/default/wombat.js"> </script>' in buff

    # JS location rewritten, JS link NOT rewritten
    assert 'window.WB_wombat_location = "http:\/\/example.com/dynamic_page.html"' in buff

    # still link rewrite in HTML
    assert '"/pywb/20131226101010/http://example.com/some/path/another.html"' in buff

def test_example_1():
    status_headers, buff = get_rewritten('http://example.com/', urlrewriter, req_headers={'Connection': 'close'})

    # verify header rewriting
    assert (('X-Archive-Orig-connection', 'close') in status_headers.headers), status_headers

    assert '/pywb/20131226101010/http://www.iana.org/domains/example' in buff, buff

def test_example_2_redirect():
    status_headers, buff = get_rewritten('http://httpbin.org/redirect-to?url=http://example.com/', urlrewriter)

    # redirect, no content
    assert status_headers.get_statuscode() == '302'
    assert len(buff) == 0


def test_example_3_rel():
    status_headers, buff = get_rewritten('//example.com/', urlrewriter)
    assert status_headers.get_statuscode() == '200'


def test_example_4_rewrite_err():
    # may occur in case of rewrite mismatch, the /// gets stripped off
    status_headers, buff = get_rewritten('http://localhost:8080///example.com/', urlrewriter)
    assert status_headers.get_statuscode() == '200'

def test_example_domain_specific_3():
    status_headers, buff = get_rewritten('http://facebook.com/digitalpreservation', urlrewriter, follow_redirects=True)

    # comment out bootloader
    assert '/* Bootloader.configurePage' in buff

def test_wombat_top():
    #status_headers, buff = get_rewritten('https://assets-cdn.github.com/assets/github-0f06d0f46fe7bcfbf31f2380f23aec15ba21b8ec.js', urlrewriter)
    status_headers, buff = get_rewritten(get_test_dir() + 'text_content/toptest.js', urlrewriter)

    assert 'WB_wombat_top!==window' in buff

def test_post():
    buff = BytesIO('ABC=DEF')

    env = {'REQUEST_METHOD': 'POST',
           'HTTP_ORIGIN': 'http://httpbin.org',
           'HTTP_HOST': 'httpbin.org',
           'wsgi.input': buff}

    status_headers, resp_buff = get_rewritten('http://httpbin.org/post', urlrewriter, env=env)
    assert status_headers.get_statuscode() == '200', status_headers


def get_rewritten(*args, **kwargs):
    return LiveRewriter().get_rewritten(*args, **kwargs)
