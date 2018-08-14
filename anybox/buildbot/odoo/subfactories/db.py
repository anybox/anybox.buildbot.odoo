from buildbot.steps.shell import ShellCommand
from buildbot.process.properties import WithProperties
from buildbot.process.properties import Property


def simple_create(configurator, options, environ=()):
    steps = []
    steps.append(ShellCommand(
        command=[
            'psql', 'postgres', '-c',
            WithProperties('DROP DATABASE IF EXISTS "%(testing_db)s"'),
        ],
        name='dropdb',
        description=["dropdb", Property('testing_db')],
        env=environ,
        haltOnFailure=True,
    ))

    steps.append(ShellCommand(
        command=[
            'psql', 'postgres', '-c',
            WithProperties('CREATE DATABASE "%%(testing_db)s" '
                           'TEMPLATE "%s"' % options.get('db_template',
                                                         'template1')),
        ],
        name='createdb',
        description=["createdb", Property('testing_db')],
        env=environ,
        haltOnFailure=True,
    ))
    steps.append(ShellCommand(
        command=[
            'psql', 'postgres', '-d', '%s' % (Property('testing_db')), '-c',
            WithProperties(
                "INSERT INTO ir_mail_server "
                "(smtp_host, smtp_port, name, smtp_encryption) VALUES "
                "('disabled.test', 25, "
                "'Disabled (adresses in .test are unroutable)', 'none'"
            ),
        ],
        name='create_disabled_outgoing_mail_server',
        description=["create_disabled_outgoing_mail_server", Property('testing_db')],
        env=environ,
        haltOnFailure=True,
    ))
    return steps


def final_dropdb(configurator, options, environ=()):
    return [
        ShellCommand(
            command=[
                'psql', 'postgres', '-c',
                WithProperties('DROP DATABASE IF EXISTS "%(testing_db)s"'),
            ],
            name='final_dropdb',
            description=["dropdb", Property('testing_db')],
            env=environ,
            haltOnFailure=False,
            flunkOnFailure=False,
        )]

simple_create.final_cleanup_steps = final_dropdb


def pg_remote_copy(configurator, options, environ=()):
    """Use a custom tailored script (a "pg_remote_copy") to mount the DB.

    This is meant for local policy dependent scripts able to remount dumps,
    but may be used for any script able to create a DB, provided buildbot can
    pass the wished database name

    options:

    :pg_remote_copy.arguments: arguments to pass (required).
                               will be simply splitted.
    :pg_remote_copy.executable: path to executable, defaults to
                                ``pg_remote_copy``.
    :pg_remote_copy.db_option: option to use to specify the target
                               database name, defaults to ``--copied_db_name``.
                               Set to None for no option
                               (db name will be a simple positional argument).
    :pg_remote_copy.timeout: time (seconds) allowed to complete the step.
                             Default is to use buildbot's default (1200 at the
                             time of this writing).
    """

    steps = []
    steps.append(ShellCommand(
        command=[
            'psql', 'postgres', '-c',
            WithProperties('DROP DATABASE IF EXISTS "%(testing_db)s"'),
        ],
        name='dropdb',
        description=["dropdb", Property('testing_db')],
        env=environ,
        haltOnFailure=True,
    ))

    copy_cmd = [options.get('pg_remote_copy.executable',
                            'pg_remote_copy')]
    db_name_opt = options.get('pg_remote_copy.db_option',
                              '--copied_db_name',)
    if db_name_opt is not None:
        copy_cmd.append(db_name_opt)
    copy_cmd.append(Property('testing_db'))

    copy_cmd.extend(options['pg_remote_copy.arguments'].split())

    timeout = options.get('pg_remote_copy.timeout')
    if timeout is not None:
        timeout = int(timeout.strip())

    steps.append(ShellCommand(
        command=copy_cmd,
        name='pg_remote_copy',
        description='pg_remote_copy',
        env=environ,
        haltOnFailure=True,
        timeout=timeout,
    ))
    return steps

pg_remote_copy.final_cleanup_steps = final_dropdb
