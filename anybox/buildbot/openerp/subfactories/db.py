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
    return steps


def pg_remote_copy(configurator, options, environ=()):
    """Use a custom tailored script (a "pg_remote_copy") to mount the DB.

    This is meant for local policy dependent scripts able to remount dumps,
    but may be used for any script able to create a DB, provided buildbot can
    pass the wished database name

    options: ``pg_remote_copy.arguments``: arguments to pass (required)
             will be simply splitted.
             ``pg_remote_copy.executable``: path to executable, defaults to
             ``pg_remote_copy``.
             ``pg_remote_copy.db_option``: option to use to specify the target
             database name, defaults to ``--copied_db_name``. Set to None for
             no option (db name will be a simple positional argument).
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

    steps.append(ShellCommand(
        command=copy_cmd,
        name='pg_remote_copy',
        description='pg_remote_copy',
        env=environ,
        haltOnFailure=True,
    ))
    return steps
