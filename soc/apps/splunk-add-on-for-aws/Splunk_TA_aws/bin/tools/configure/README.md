
# AWS Add-on configuration Tool

### Usage
Environment variable `SPLUNK_HOME` is required. Generally the usage is similar to `aws cli`

```
$ python aws_config_cli.py -h
usage: aws_config_cli.py [-h]
                         {account, iam-role,private-account,billing-cost,cloudtrail,cloudtrail-lake,cloudwatch,cloudwatch-logs,config,config-rules,incr-s3,inspector,inspector_v2,kinesis,metadata,s3,sqs-based-s3,sqs,all}
                         ...

AWS AddOn configuration tool

positional arguments:
  {account, iam-role,private-account,billing-cost,cloudtrail,cloudtrail-lake,cloudwatch,cloudwatch-logs,config,config-rules,incr-s3,inspector,inspector_v2,kinesis,metadata,s3,sqs-based-s3,sqs,all}
                        Pick which resource to manipulate
    account             account AWS account setting subcommand
    iam-role            iam-role AWS IAM role setting subcommand
    private-account     private AWS account setting subcommand
    billing-cost        billing-cost modinput data input subcommand
    cloudtrail          cloudtrail modinput data input subcommand
    cloudtrail-lake     cloudtrail-lake modinput data input subcommand
    cloudwatch          cloudwatch modinput data input subcommand
    cloudwatch-logs     cloudwatch-logs modinput data input subcommand
    config              config modinput data input subcommand
    config-rules        config-rules modinput data input subcommand
    incr-s3             incr-s3 modinput data input subcommand
    inspector           inspector modinput data input subcommand
    inspector_v2        inspector_v2 modinput data input subcommand
    kinesis             kinesis modinput data input subcommand
    metadata            metadata modinput data input subcommand
    s3                  s3 modinput data input subcommand
    sqs-based-s3        sqs-based-s3 modinput data input subcommand
    sqs                 sqs modinput data input subcommand
    all                 Create all resources specified in conf file which can
                        contain different resources and different hostnames

optional arguments:
  -h, --help            show this help message and exit
```

### Sub command usage
Issue subcommand -h, for instance

```
$python aws_config_cli.py s3 -h
usage: aws_config_cli.py s3 [-h] {create,list,delete} ...

positional arguments:
  {create,list,delete}  create|list|delete modinput data input
    create              Create modinput data input
    list                List modinput data input
    delete              Delete modinput data input

optional arguments:
  -h, --help            show this help message and exit
```

```
$python aws_config_cli.py s3 create -h
usage: aws_config_cli.py s3 create [-h] --hostname HOSTNAME --config-file
                                   CONFIG_FILE [--dry-run]

optional arguments:
  -h, --help            show this help message and exit
  --hostname HOSTNAME   Splunk hostname
  --config-file CONFIG_FILE
                        Stanza configuration file, refer to
                        config_examples/s3-inputs.json for example
  --dry-run             Dry run just validate the configurations
```

### Tool's config files
The tool relies on some its own configuration files to do AWS AddOn data input or other settings' configuration.

#### splunk-info.json
Contains splunk credentials which are used to create data inputs. For example:

```
[
  {
    "hostname": "hfw-01",
    "mgmt_uri": "https://ghost:8089",
    "username": "admin",
    "password": "admin"
  },
  {
    "hostname": "hfw-02",
    "mgmt_uri": "https://ghost:8089",
    "username": "admin",
    "password": "admin"
  }
]
```

#### rest_specs
The directory contains all REST APIs supported by this tool. The spec files are readonly and should not be modified by end users. They are used to validate users configuration when creating data inputs.
When creating data inputs like in `config_examples`, users need refer these spec files since the spec files declare all fields that a data input support and some of them are required.

```
$ls rest_specs
account-settings.json.spec
iam-role-settings.json.spec
private-account-settings.json.spec
billing-cost-inputs.json.spec
cloudtrail-inputs.json.spec
cloudtrail-lake-inputs.json.spec
cloudwatch-inputs.json.spec
cloudwatch-logs-inputs.json.spec
config-inputs.json.spec
config-rules-inputs.json.spec
incr-s3-inputs.json.spec
inspector-inputs.json.spec
inspector_v2-inputs.json.spec
kinesis-inputs.json.spec
metadata-inputs.json.spec
s3-inputs.json.spec
sqs-based-s3-inputs.json.spec
sqs-inputs.json.spec
```

####
### Examples

#### config_examples directory
Example files. They can be used as a template by user and twist according their own needs.

Note, config file will be validated by this tool. For instance if a required field is missing in config file which are used to create data input, the tool will report error

#### Create inputs

1. Create AWS account on `hfw-01`
```
$ python aws_config_cli.py account create --hostname hfw-01 --config-file config_examples/account-settings.json
```

2. Create Private AWS account on `hfw-01`
```
$ python aws_config_cli.py private-account create --hostname hfw-01 --config-file config_examples/private-account-settings.json
```

3. Create S3 data inputs on `hfw-01`
```
$ python aws_config_cli.py s3 create --hostname hfw-01 --config-file config_examples/s3-inputs.json
```

4. Create kinesis data inputs on `hfw-01`
```
$ python aws_config_cli.py kinesis create --hostname hfw-01 --config-file config_examples/kinesis-inputs.json
```

- Similarly for any other data inputs `{ account, iam-role, private-account, billing-cost, cloudtrail, cloudtrail-lake, cloudwatch, cloudwatch-logs, config, config-rules, incr-s3, inspector, inspector_v2, kinesis, metadata, s3, sqs-based-s3, sqs }`

#### List inputs

1. List all S3 data inputs on `hfw-01`
```
$ python aws_config_cli.py s3 list --hostname hfw-01
```

2. List specific S3 data inputs on `hfw-01`
```
$ python aws_config_cli.py s3 list --hostname hfw-01 --names s3-01
```

#### Delete inputs

1. Delete S3 data inputs specified on `hfw-01`
```
$ python aws_config_cli.py s3 delete --hostname hfw-01 --names s3-01
```

2. Delete 2 AWS account on `hfw-01`
```
$ python aws_config_cli.py account delete --hostname hfw-01 --name aws-account-0,aws-account-1
```
#### Validate inputs

1. Dry run which only validates the configuration instead of commits the data inputs
```
python aws_config_cli.py s3 create --hostname hfw-01 --config-file config_examples/s3-inputs.json --dry-run
```

#### Create many inputs

1. Create all settings and data inputs in one shot
```
$ python aws_config_cli.py all create --config-file config_examples/all.json
```
