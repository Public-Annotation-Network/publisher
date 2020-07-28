PAN Publisher REST API
======================

This repository contains the reference implementation for a Public Annotations Network (PAN)
publisher service. Annotations can be directly published through Ethereum and IPFS. However,
sending an Ethereum transaction for each annotation can become expensive. Publisher services
try to solve this issue by providing an easy-to-use REST API, which allows for batched
submissions - reducing the overall cost - as wel as easier access to Ethereum- and IPFS-related
annotation data.

Example Usage
-------------

Paginate through all the published annotations in the system with `limit` and `offset`:

```shell script
$ http GET http://localhost:8000/annotations/\?limit\=1
HTTP/1.1 200 OK
Connection: close
Date: Tue, 28 Jul 2020 16:35:17 GMT
Server: gunicorn/20.0.4
content-length: 612
content-type: application/json

[
    {
        "@context": [
            "https://pan.network/annotation/v1"
        ],
        "credentialSubject": {
            "annotation": "text..",
            "content": "uri:tweet:joaosantos/1281904943700619265"
        },
        "issuanceDate": "2010-01-01T19:23:24Z",
        "issuer": "urn:ethereum:0x7DaD14B10Ccf71B480883A20DD4906058a70762e",
        "proof": {
            "created": "2017-06-18T21:19:10Z",
            "jws": "0xea0ab3cd7b69751a5ac656dd73aab41b3e40304b7f8fee09658b44f9a273ed5c08b73633c72de24fb55cc7280d02f264832b360181399c7722388817ef9ce0201c",
            "proofPurpose": "PANSubmission",
            "type": "EthereumECDSA",
            "verificationMethod": "urn:ethereum:messageHash"
        },
        "type": [
            "VerifiableCredential",
            "PANCredential"
        ]
    }
]
```

For more parameters, check out the OpenAPI spec in this repo!


Installation and Deployment
---------------------------

To set up the publisher service, Docker above version 19, and Docker Compose > 1.25.0 are
recommended. Running the following command in the project root should take care of the
deployment:

```shell script
docker-compose up --build -d
```

This will build the API Dockerfile, install all dependencies, and run it along the following
stack components:

- Postgres (for storage of unpublished annotations)
- Redis (handling async background jobs)
- celery (managing and scheduling background jobs)
- flower (visualizing and monitoring background jobs)


Future Work
-----------

- incentive model around publishers
    - user model and authentication/authorization
    - publishers can ask for fees
    - users can determine a price they want to pay for the annotation to get in
    - publishers can return signed receipts (i.e. promises for an annotation to be published)
- better publishing modes (fixed-size batch mode vs. periodic time frame mode)
- documentation and tests
