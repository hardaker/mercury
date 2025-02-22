/*
 * extractor.h
 *
 * Copyright (c) 2019 Cisco Systems, Inc. All rights reserved.
 * License at https://github.com/cisco/mercury/blob/master/LICENSE
 */

#ifndef EXTRACTOR_H
#define EXTRACTOR_H

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>      /* for FILE */
#include "mercury.h"


enum packet_data_type {
    packet_data_type_none            = 0,
    packet_data_type_tls_sni         = 1,
    packet_data_type_http_user_agent = 2
};

struct packet_data {
    enum packet_data_type type;
    size_t length;
    const uint8_t *value;
};

enum fingerprint_type {
    fingerprint_type_unknown    = 0,
    fingerprint_type_tcp        = 1,
    fingerprint_type_tls        = 2,
    fingerprint_type_tls_sni    = 3,
    fingerprint_type_tls_server = 4,
    fingerprint_type_http       = 5,
    fingerprint_type_http_server = 6
};

#define PROTO_UNKNOWN 65535

struct protocol_state {
    uint16_t proto;   /* protocol IANA number */
    uint16_t dir;     /* DIR_CLIENT, DIR_SERVER, DIR_UNKNOWN */
    uint32_t state;   /* protocol-specific state */
};

/*
 * state represents the state of the extractor; it knows whether or
 * not additional packets must be processed, etc.
 */
typedef enum extractor_state {
    state_done = 0,
    state_start = 1,
    state_not_done = 2
} extractor_state_e;


/*
 * An extractor is an object that parses data in one buffer, selects
 * some of the data fields and writes them into a second output
 * buffer.  An extractor maintains a pointers into the data buffer
 * (from where the next byte will be read) and into the output buffer
 * (to where the next copied byte will be written).  Its method
 * functions perform all of the necessary bounds checking to ensure
 * that all of the reading and writing operations respect buffer
 * bounaries.  Some operations advance both the data and output
 * pointers, while others advance just the data pointer or just the
 * output pointer, and others advance neither.
 *
 * Some data formats require the parsing of a variable-length data
 * field, whose length is encoded in the data.  To facilitate this, a
 * second 'inner' extractor can be pushed on top of an extractor with
 * the extractor_push function, which initializes the inner extractor
 * to read from the data buffer defined by the variable-length field.
 * After the inner data has been read, a call to extractor_pop updates
 * the outer extractor appropriately.
 *
 * For protocol fingerprinting, the data copied into the output buffer
 * should contain enough information that it can be parsed without the
 * help of any additional information.
 *
 */
struct extractor {
    enum fingerprint_type fingerprint_type;
    struct protocol_state proto_state;  /* tracking across packets   */
    unsigned char *output_start;        /* buffer for output         */
    unsigned char *output;              /* buffer for output         */
    unsigned char *output_end;          /* end of output buffer      */
    unsigned char *last_capture;        /* last cap in output stream */
    struct packet_data packet_data;     /* data of interest in packt */
};

struct parser {
    const unsigned char *data;          /* data being parsed/copied  */
    const unsigned char *data_end;      /* end of data buffer        */
};

// enum status {
//     status_ok  = 0,
//     status_err = 1
// };

/*
 * extractor_is_not_done(x) returns 0 if the extractor is
 * done parsing a flow, and otherwiwse returns another value.
 *
 */
extractor_state_e extractor_is_not_done(const struct extractor *x);


/*
 * extractor_init(x) initializes the state machine associated with x,
 * and an output buffer (to which selected data will be copied)
 *
 */
void extractor_init(struct extractor *x,
		    unsigned char *output,
		    unsigned int output_len);

/*
 * parser_init initializes a parser object with a data buffer
 * (holding the data to be parsed)
 */
void parser_init(struct parser *p, 
		 const unsigned char *data,
		 unsigned int data_len);


/*
 * extractor_skip advances the data pointer by len bytes, but does not
 * advance the output pointer.  It does not copy any data.
 */
enum status extractor_skip(struct extractor *x,
			   unsigned int len);

/*
 * extractor_skip_to advances the data pointer to the location
 * provided as input, but does not advance the output pointer.  It
 * does not copy any data.
 */
enum status extractor_skip_to(struct extractor *x,
			      const unsigned char *location);

/*
 * extractor_copy copies data from the data buffer to the output
 * buffer, after prepending the length of that data, and advances both
 * the data pointer and the output pointer.
 */
enum status parser_extractor_copy(struct parser *p,
				  struct extractor *x,
				  unsigned int len);


/*
 * extractor_copy_append copies data from the data buffer to the
 * output buffer, after updating the length of the previously copied
 * data, then advances both the data pointer and the output pointer.
 */
enum status extractor_copy_append(struct extractor *x,
				  unsigned int len);

 /*
 * extractor_read_uint reads the next num_bytes from the data buffer,
 * interprets them as an unsigned integer in network byte (big endian)
 * order, and writes the resulting value into the size_t at
 * uint_output.  Neither the data pointer nor output pointer are
 * advanced.
 */
enum status extractor_read_uint(struct extractor *x,
				unsigned int num_bytes,
				size_t *uint_output);


/*
 * extractor_push initializes the extractor inner with the current
 * data and output pointers of extractor outer, with the data buffer
 * restricted to the number of bytes indicated by the length parameter
 */
enum status extractor_push(struct extractor *inner,
			   const struct extractor *outer,
			   size_t length);

/*
 * extractor_pop removes the inner extractor and updates the outer
 * extractor appropriately.  The length of data copied into the output
 * buffer is encoded into the appropriate location of that buffer;
 * that is, this function ensures that the variable-length field
 * copied into the output buffer is accurate and complete.
 */
void extractor_pop(struct extractor *outer,
		   const struct extractor *inner);

/*
 * extractor_reserve_output reserves num_bytes bytes of the output
 * stream as the location to which data can be written in the future,
 * and remembers that location (by storing it into its tmp_location
 * variable).  This function can be used to encode variable-length
 * data in the output (and it is used by extractor_push and
 * extractor_pop).
 */
enum status extractor_reserve_output(struct extractor *x,
				     size_t num_bytes);

/*
 * extractor_get_data_length returns the number of bytes remaining in
 * the data buffer.  Callers should expect that the value returned may
 * be negative.
 */
ptrdiff_t extractor_get_data_length(struct extractor *x);

/*
 * extractor_get_output_length returns the number of bytes of output
 * that have been written into the output buffer.
 */
ptrdiff_t extractor_get_output_length(const struct extractor *x);

enum status extractor_push_vector_extractor(struct extractor *y,
					    struct extractor *x,
					    size_t bytes_in_length_field);

void extractor_pop_vector_extractor(struct extractor *x,
				    struct extractor *y);

enum status extractor_copy_alt(struct extractor *x,
			       unsigned char *data, /* alternative data source */
			       unsigned int len);

unsigned int match(const unsigned char *data,
		   size_t data_len,
		   const unsigned char *mask,
		   const unsigned char *value,
		   size_t value_len);


unsigned int extractor_match(struct extractor *x,
			     const unsigned char *value,
			     size_t value_len,
			     const unsigned char *mask);

unsigned int uint16_match(uint16_t x,
			  const uint16_t *ulist,
			  unsigned int num);


/*
 * protocol-specific functions
 */


unsigned int parser_extractor_process_tcp_data(struct parser *p, struct extractor *x);

unsigned int extractor_process_tcp(struct extractor *x);

const char *get_frame_type(const unsigned char *data,
			   unsigned int len);



/*
 * new functions for mercury
 */


unsigned int parser_extractor_process_packet(struct parser *p, struct extractor *x);

unsigned int parser_extractor_process_tls(struct parser *p, struct extractor *x);

unsigned int parser_process_tls_server(struct parser *p);


/*
 * extract_fp_from_tls_client_hello() runs the fingerprint extraction
 * algorithm on the byte string start at the location *data* and
 * continuing for *data_len* bytes, and if there is a well-formed TLS
 * clientHello in that buffer, the normalized fingerprint is extracted
 * and the resulting string is written into outbuf, as a parenthesized
 * hexadecimal string, as long as it fits in the output buffer (has
 * length less than outbuf_len).
 *
 * RETURN VALUE: the number of (single-byte) characters written into
 * the output buffer, or zero on failure.
 * 
 */
size_t extract_fp_from_tls_client_hello(uint8_t *data,
					size_t data_len,
					uint8_t *outbuf,
					size_t outbuf_len);


void parser_init_packet(struct parser *p, const unsigned char *data, unsigned int length);


#endif /* EXTRACTOR_H */
