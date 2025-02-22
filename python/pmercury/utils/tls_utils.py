"""     
 Copyright (c) 2019 Cisco Systems, Inc. All rights reserved.
 License at https://github.com/cisco/mercury/blob/master/LICENSE
"""

import os
import ast
import sys
import gzip

import ujson as json

from collections import OrderedDict
from binascii import hexlify, unhexlify

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from tls_constants import *
from pmercury_utils import *

grease_ = set(['0a0a','1a1a','2a2a','3a3a','4a4a','5a5a','6a6a','7a7a',
               '8a8a','9a9a','aaaa','baba','caca','dada','eaea','fafa'])


ext_data_extract_ = set(['0001','0005','0007','0008','0009','000a','000b',
                         '000d','000f','0010','0011','0013','0014','0018',
                         '001b','001c','002b','002d','0032','5500'])
ext_data_extract_ = ext_data_extract_.union(grease_)


imp_date_cs_file = find_resource_path('resources/implementation_date_cs.json.gz')
with gzip.open(imp_date_cs_file,'r') as fp:
    imp_date_cs_data = json.loads(fp.read())

imp_date_ext_file = find_resource_path('resources/implementation_date_ext.json.gz')
with gzip.open(imp_date_ext_file,'r') as fp:
    imp_date_ext_data = json.loads(fp.read())


def extract_server_name(data):
    if len(data) < 7:
        return 'None'
    sni_len = int(hexlify(data[5:7]),16)
    return str(data[7:7+sni_len],'utf-8')


def hex_fp_to_structured_representation(s):
    xtn_grease_list = [
        10,        # supported_groups
        11,        # ec_point_formats
        13,        # signature_algorithms
        43         # supported_versions  
    ]
    output = ''

    # parse protocol version 
    output += '(' + str(s[0:4], 'utf-8') + ')'

    # parse ciphersuite offer vector
    cs_len = s[4:8]
    output += '('
    cs_data_len = int(cs_len, 16)*2    
    cs_vec = s[8:8+cs_data_len]
    output += str(cs_vec, 'utf-8') + ')'

    if len(s) <= 8+cs_data_len:
        return output

    # parse client extensions
    ext_index = 8+cs_data_len
    ext_len = s[ext_index:ext_index+4]
    output += '('
    ext_data_len = int(ext_len, 16)*2 
    ext_data = s[ext_index+4:ext_index+4+ext_data_len]
    x_index = 0
    while x_index + 8 <= len(ext_data):
        x_type = ext_data[x_index+0:x_index+4]
        x_len  = ext_data[x_index+4:x_index+8]
        x_index_next = x_index + int(x_len, 16) * 2 + 8
        x_data = ext_data[x_index+8:x_index_next]
        x_index = x_index_next
        output += '('
        output += str(x_type, 'utf-8')
        if str(x_type, 'utf-8') in ext_data_extract_:
            output += str(x_len, 'utf-8')
            output += str(x_data, 'utf-8')
        output += ')'
    output += ')'

    return output


def hex_fp_to_structured_representation_server(s):
    output = ''

    # parse protocol version 
    output += '(' + str(s[0:4], 'utf-8') + ')'

    # parse selected cipher suite
    scs_ = s[4:8]
    output += '(' + str(s[4:8], 'utf-8') + ')'

    # parse client extensions
    ext_index = 8
    ext_len = s[ext_index:ext_index+4]
    output += '('
    ext_data_len = int(ext_len, 16)*2 
    ext_data = s[ext_index+4:ext_index+4+ext_data_len]
    x_index = 0
    while x_index + 8 <= len(ext_data):
        x_type = ext_data[x_index+0:x_index+4]
        x_len  = ext_data[x_index+4:x_index+8]
        x_index_next = x_index + int(x_len, 16) * 2 + 8
        x_data = ext_data[x_index+8:x_index_next]
        x_index = x_index_next
        output += '('
        output += str(x_type, 'utf-8')
        if str(x_type, 'utf-8') in ext_data_extract_:
            output += str(x_len, 'utf-8')
            output += str(x_data, 'utf-8')
        output += ')'
    output += ')'

    return output


def eval_fp_str(fp_str_):
    fp_str_ = '(' + str(fp_str_, 'utf-8') + ')'
    fp_str_ = fp_str_.replace('(','["').replace(')','"]').replace('][','],[')
    new_str_ = fp_str_.replace('["[','[[').replace(']"]',']]')
    while new_str_ != fp_str_:
        fp_str_ = new_str_
        new_str_ = fp_str_.replace('["[','[[').replace(']"]',']]')
    return ast.literal_eval(fp_str_)


def get_version_from_str(version_str_, convert=True):
    if version_str_ in TLS_VERSION and convert:
        return TLS_VERSION[version_str_]
    else:
        return version_str_


def get_cs_from_str(cs_str_, convert=True):
    cs_l_ = []
    for i in range(0,len(cs_str_),4):
        cs_ = cs_str_[i:i+4]
        if cs_ in imp_date_cs_data and convert:
            cs_l_.append(imp_date_cs_data[cs_]['name'])
        else:
            cs_l_.append(cs_)
    return cs_l_


def get_ext_from_str(exts_, convert=True):
    ext_l_ = []
    for ext in exts_:
        if len(ext) == 0:
            break
        ext_type_ = ext[0][0:4]
        ext_type_str_kind = str(int(ext_type_,16))
        if ext_type_str_kind in imp_date_ext_data and convert:
            ext_type_ = imp_date_ext_data[ext_type_str_kind]['name']
        ext_data_ = ''
        if len(ext[0]) > 4 and convert:
            ext_data_ = parse_extension_data(ext_type_, ext[0][4:])
        elif len(ext[0]) > 4:
            ext_data_ = ext[0][4:]

        ext_l_.append({ext_type_: ext_data_})

    return ext_l_


def get_implementation_date(cs_str_): # @TODO: add extension
    dates_ = set([])
    for i in range(0,len(cs_str_),4):
        cs_ = cs_str_[i:i+4]
        if cs_ in imp_date_cs_data:
            dates_.add(imp_date_cs_data[cs_]['date'])
    dates_ = list(dates_)
    dates_.sort()
    return dates_[-1], dates_[0]


def parse_extension_data(ext_type, ext_data_):
    ext_len = int(ext_data_[0:4],16)
    ext_data = ext_data_[4:]

    if ext_type == 'application_layer_protocol_negotiation':
        ext_data = parse_application_layer_protocol_negotiation(ext_data, ext_len)
    elif ext_type == 'signature_algorithms':
        ext_data = signature_algorithms(ext_data, ext_len)
    elif ext_type == 'status_request':
        ext_data = status_request(ext_data, ext_len)
    elif ext_type == 'ec_point_formats':
        ext_data = ec_point_formats(ext_data, ext_len)
    elif ext_type == 'key_share':
        ext_data = key_share_client(ext_data, ext_len)
    elif ext_type == 'psk_key_exchange_modes':
        ext_data = psk_key_exchange_modes(ext_data, ext_len)
    elif ext_type == 'supported_versions':
        ext_data = supported_versions(ext_data, ext_len)
    elif ext_type == 'supported_groups':
        ext_data = supported_groups(ext_data, ext_len)

    return ext_data


# helper to parse/extract/skip single extension
def parse_extension(data, offset):
    tmp_ext_type = degrease_type_code(data, offset)
    fp_ext_ = tmp_ext_type
    offset += 2
    ext_len = int(str(hexlify(data[offset:offset+2]), 'utf-8'),16)
    tmp_ext_len = unhexlify(('%04x' % (ext_len)))
    offset += 2
    tmp_ext_value = data[offset:offset+ext_len]
    if str(hexlify(tmp_ext_type), 'utf-8') in ext_data_extract_:
        tmp_ext_value = degrease_ext_data(data, offset, tmp_ext_type, ext_len, tmp_ext_value)
        fp_ext_ += tmp_ext_len
        fp_ext_ += tmp_ext_value
    else:
        fp_ext_ += unhexlify(('%04x' % 0))
    offset += ext_len

    return fp_ext_, offset, ext_len

# helper to normalize grease type codes
def degrease_type_code(data, offset):
    if str(hexlify(data[offset:offset+2]), 'utf-8') in grease_:
        return unhexlify('0a0a')
    else:
        return data[offset:offset+2]


# helper to normalize grease within supported_groups and supported_versions
def degrease_ext_data(data, offset, ext_type, ext_length, ext_value):
    if str(hexlify(ext_type), 'utf-8') == '000a': # supported_groups
        degreased_ext_value = data[offset:offset+2]
        for i in range(2,ext_length,2):
            if str(hexlify(data[offset+i:offset+i+2]), 'utf-8') in grease_:
                degreased_ext_value += unhexlify('0a0a')
            else:
                degreased_ext_value += data[offset+i:offset+i+2]
        return degreased_ext_value
    elif str(hexlify(ext_type), 'utf-8') == '002b': # supported_versions
        degreased_ext_value = data[offset:offset+1]
        for i in range(1,ext_length,2):
            if str(hexlify(data[offset+i:offset+i+2]), 'utf-8') in grease_:
                degreased_ext_value += unhexlify('0a0a')
            else:
                degreased_ext_value += data[offset+i:offset+i+2]
        return degreased_ext_value

    return ext_value


def supported_groups(data, length):
    if len(data) < 2:
        return ''
    info = OrderedDict({})
    data = unhexlify(data)
    ext_len = int(str(hexlify(data[0:2]), 'utf-8'),16)
    info['supported_groups_list_length'] = ext_len
    info['supported_groups'] = []
    offset = 2
    while offset < length:
        tmp_data = str(hexlify(data[offset:offset+2]), 'utf-8')
        info['supported_groups'].append(TLS_SUPPORTED_GROUPS[int(tmp_data,16)])
        offset += 2

    return info


def supported_versions(data, length):
    if len(data) < 2:
        return ''
    info = OrderedDict({})
    data = unhexlify(data)
    ext_len = int(str(hexlify(data[0:1]), 'utf-8'),16)
    info['supported_versions_list_length'] = ext_len
    info['supported_versions'] = []
    offset = 1
    while offset < length:
        tmp_data = str(hexlify(data[offset:offset+2]), 'utf-8')
        if tmp_data in TLS_VERSION:
            info['supported_versions'].append(TLS_VERSION[tmp_data])
        else:
            info['supported_versions'].append('Unknown Version (%s)' % tmp_data)
        offset += 2

    return info


def psk_key_exchange_modes(data, length):
    if len(data) < 2:
        return ''
    info = OrderedDict({})
    data = unhexlify(data)
    ext_len = int(str(hexlify(data[0:1]), 'utf-8'),16)
    info['psk_key_exchange_modes_length'] = ext_len
    mode = int(str(hexlify(data[1:2]), 'utf-8'),16)
    info['psk_key_exchange_mode'] = TLS_PSK_KEY_EXCHANGE_MODES[mode]

    return info


def key_share_client(data, length):
    if len(data) < 2:
        return ''
    info = OrderedDict({})
    data = unhexlify(data)
    ext_len = int(str(hexlify(data[0:2]), 'utf-8'),16)
    info['key_share_length'] = ext_len
    info['key_share_entries'] = []
    offset = 2
    while offset < length:
        tmp_obj = OrderedDict({})
        tmp_data = str(hexlify(data[offset:offset+2]), 'utf-8')
        tmp_obj['group'] = TLS_SUPPORTED_GROUPS[int(tmp_data,16)]
        tmp_obj['key_exchange_length'] = int(str(hexlify(data[offset+2:offset+4]), 'utf-8'),16)
        tmp_obj['key_exchange'] = str(hexlify(data[offset+4:offset+4+tmp_obj['key_exchange_length']]), 'utf-8')
        info['key_share_entries'].append(tmp_obj)
        offset += 4 + tmp_obj['key_exchange_length']

    return info


def ec_point_formats(data, length):
    if len(data) < 2:
        return ''
    info = OrderedDict({})
    data = unhexlify(data)
    ext_len = int(str(hexlify(data[0:1]), 'utf-8'),16)
    info['ec_point_formats_length'] = ext_len
    info['ec_point_formats'] = []
    for i in range(ext_len):
        if str(hexlify(data[i+1:i+2]), 'utf-8') in TLS_EC_POINT_FORMATS:
            info['ec_point_formats'].append(TLS_EC_POINT_FORMATS[str(hexlify(data[i+1:i+2]), 'utf-8')])
        else:
            info['ec_point_formats'].append(str(hexlify(data[i+1:i+2]), 'utf-8'))

    return info


def status_request(data, length):
    if len(data) < 2:
        return ''
    info = OrderedDict({})
    data = unhexlify(data)
    info['certificate_status_type'] = TLS_CERTIFICATE_STATUS_TYPE[str(hexlify(data[0:1]), 'utf-8')]
    offset = 1
    info['responder_id_list_length'] = int(str(hexlify(data[offset:offset+2]), 'utf-8'),16)
    offset += info['responder_id_list_length'] + 2
    info['request_extensions_length'] = int(str(hexlify(data[offset:offset+2]), 'utf-8'),16)
    offset += info['request_extensions_length'] + 2

    return info


def signature_algorithms(data, length):
    if len(data) < 2:
        return ''
    info = OrderedDict({})
    data = unhexlify(data)
    ext_len = int(str(hexlify(data[0:2]), 'utf-8'),16)
    info['signature_hash_algorithms_length'] = ext_len
    info['algorithms'] = []
    offset = 2
    while offset < length:
        tmp_data = str(hexlify(data[offset:offset+2]), 'utf-8')
        if tmp_data in TLS_SIGNATURE_HASH_ALGORITHMS:
            info['algorithms'].append(TLS_SIGNATURE_HASH_ALGORITHMS[tmp_data])
        else:
            info['algorithms'].append('unknown(%s)' % tmp_data)
        offset += 2

    return info


def parse_application_layer_protocol_negotiation(data, length):
    data = unhexlify(data)
    alpn_len = int(str(hexlify(data[0:2]), 'utf-8'),16)
    alpn_offset = 2
    alpn_data = []
    while alpn_offset < length:
        tmp_alpn_len = int(str(hexlify(data[alpn_offset:alpn_offset+1]), 'utf-8'),16)
        alpn_offset += 1
        alpn_data.append(data[alpn_offset:alpn_offset+tmp_alpn_len])
        alpn_offset += tmp_alpn_len

    return alpn_data


def get_tls_params(fp_):
    cs_ = []
    for i in range(0,len(fp_[1][0]),4):
        cs_.append(fp_[1][0][i:i+4])
    cs_4_ = get_ngram(cs_, 4)

    ext_ = []
    if len(fp_) > 2 and fp_[2] != ['']:
        for t_ext_ in fp_[2]:
            ext_.append('ext_' + t_ext_[0][0:4] + '::' + t_ext_[0][4:])

    return [cs_4_, ext_]


def get_sequence(fp_):
    seq = []
    cs_ = fp_[1][0]
    for i in range(0,len(cs_),4):
        seq.append(cs_[i:i+4])
    ext_ = []
    if len(fp_) > 2 and fp_[2] != ['']:
        for t_ext_ in fp_[2]:
            seq.append('ext_' + t_ext_[0][0:4] + '::' + t_ext_[0][4:])
    return seq


def get_ngram(l, ngram):
    l_ = []
    for i in range(0,len(l)-ngram):
        s_ = ''
        for j in range(ngram):
            s_ += l[i+j]
        l_.append(s_)
    if len(l_) == 0:
        l_ = l
    return l_





