# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (nested_scopes, generators, division, absolute_import, with_statement,
                        print_function, unicode_literals)

from pants.base.build_environment import get_buildroot
from pants.base.build_file import BuildFile
from pants.base.target import Target
from pants.targets.jar_dependency import JarDependency
from pants.tasks.console_task import ConsoleTask
from pants.tasks.jar_publish import PushDb


class CheckPublishedDeps(ConsoleTask):

  @classmethod
  def setup_parser(cls, option_group, args, mkflag):
    super(CheckPublishedDeps, cls).setup_parser(option_group, args, mkflag)

    option_group.add_option(mkflag('print-uptodate'), mkflag('print-uptodate', negate=True),
                            dest='check_deps_print_uptodate', default=False,
                            action='callback', callback=mkflag.set_bool,
                            help='[%default] Also print up-to-date dependencies.')

  def __init__(self, context):
    ConsoleTask.__init__(self, context)

    self._print_uptodate = context.options.check_deps_print_uptodate
    self.repos = context.config.getdict('jar-publish', 'repos')
    self._artifacts_to_targets = {}
    all_addresses = (address for buildfile in BuildFile.scan_buildfiles(get_buildroot())
                     for address in Target.get_all_addresses(buildfile))
    for address in all_addresses:
      target = Target.get(address)
      if target.is_exported:
        provided_jar, _, _ = target.get_artifact_info()
        artifact = (provided_jar.org, provided_jar.name)
        if not artifact in self._artifacts_to_targets:
          self._artifacts_to_targets[artifact] = target

  def console_output(self, targets):
    push_dbs = {}

    def get_jar_with_version(target):
      db = target.provides.repo.push_db
      if db not in push_dbs:
        push_dbs[db] = PushDb.load(db)
      return push_dbs[db].as_jar_with_version(target)

    visited = set()
    for target in targets:
      for dependency in target.dependencies:
        for dep in dependency.resolve():
          if isinstance(dep, JarDependency):
            artifact = (dep.org, dep.name)
            if artifact in self._artifacts_to_targets and not artifact in visited:
              visited.add(artifact)
              artifact_target = self._artifacts_to_targets[artifact]
              _, semver, sha, _ = get_jar_with_version(artifact_target)
              if semver.version() != dep.rev:
                yield 'outdated %s#%s %s latest %s' % (dep.org, dep.name, dep.rev, semver.version())
              elif self._print_uptodate:
                yield 'up-to-date %s#%s %s' % (dep.org, dep.name, semver.version())
