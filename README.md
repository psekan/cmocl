# CMoCL
Continuous monitoring of cryptographic libraries using biased RSA keys.
Details and results available on https://rsa.sekan.eu/.

Introduction
-----

Available through docker image pesio/cmocl. Before pulling and running new container,
you need to prepare configuration file. Example of configuration file is in the file
`configuration.json`. Then use path to this file and mount it to your container.

Configuration
-----

List of configuration settings:

| Setting        | Explanation                                                            |
|----------------|------------------------------------------------------------------------|
| rapid7-api-key | API key for Rapid7 OpenData                                            |
| ct-log-url     | URL to a Certificate Transparency log without http:// or https://      |
| ct-last-entry  | Last entry of the CT log, which was already processed = 0 on beginning |
| cmocl-api-url  | URL of CMoCL storage service API                                       |
| cmocl-api-key  | API key for CMoCL storage service API                                  |
| storage-path   | You can mount a volume and store locally estimation results            |

If you would like to receive email notification with basic information, you can configure SMTP connection:

| Setting        | Explanation                                                 |
|----------------|-------------------------------------------------------------|
| smtp-host      | Host of SMTP, empty if you do not want to use notifications |
| smtp-port      | Port of SMTP server                                         |
| smtp-user      | SMTP user name                                              |
| smtp-pass      | SMTP user password                                          |
| smtp-from      | Email address set as sender                                 |
| smtp-to        | Email address of receiver                                   |

Installation
-----

```
docker pull pesio/cmocl
docker run --name cmocl -d -v $(pwd)/configuration.json:/app/configuration.json pesio/cmocl
```

If you are running pesio/rsabias image on the same host, probably you will need `--net host` 
flag in `docker run` command.

