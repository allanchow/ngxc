# -*- coding: utf-8 -*-

import logging
import sys
import shutil
import itertools
import time

import git

from .command import Command
from .utils import catch, isempty

class GitProgress(git.RemoteProgress):

    def _parse_progress_line(self, line: str) -> None:
        print(line)


class GitUtil(object):

    @staticmethod
    def is_git(cwd: str='.') -> bool:
        with catch(git.exc.InvalidGitRepositoryError, default=None) as _:
            _ = git.Repo(cwd).git_dir
            return not _ is None


class GitClean(object):

    def __get_remote_branch_name(self, branchname: str) -> str:
        try:
            # Get branch object, and resolve HEAD reference if required
            resolved_remote_branch = self.origin.refs.HEAD.reference if branchname == 'HEAD' else self.origin.refs[branchname]
        except IndexError as e:
            assert False, 'Can\'t switch to remote branch [%s] as it is not exist' % branchname
        # get remote branch name, ready for local branch use
        return resolved_remote_branch.remote_head

    # clean up index and working dir
    def __clean_untracked(self) -> None:
        # remove any untracked files
        logging.debug('Clean untracked files')
        self.repo.git.clean('-xdf')
        # clean up all local merged/non-merged that not in remotes
        for b in self.repo.heads:
            if not str(b) in self.repo.remotes.origin.refs:
                logging.info('Clean up local [%s] branch not in [%s]' % (str(b), self.repo.git_dir))
                self.repo.git.branch(['-D', str(b)])

    def __clone(self, gitpath: str, branch: str, cwd: str):
        # with progress(self.name) as p:
        #config = ['core.eol=lf', 'core.autocrlf=false', 'user.name=Builder', 'user.email=builder@gmail.com']
        config = ['--config=user.name=Builder', '--config=user.email=builder@gmail.com']
        try:
            # FIXME: Can't use gitpython as it only return receiving progress after all received, it is a problematic when it is a large git repo.
            # It seems that gitypython creates a cmd thread, and the thread.join() blocks the print output in the thread
            # see https://github.com/gitpython-developers/GitPython/blob/master/git/cmd.py line #113
            #repo = git.Repo.clone_from(url=self.git, to_path=cwd, progress=GitPRogress(), config=config, branch=self.branch)
            Command(['git', 'clone', '--branch=%s' % branch, *config, '--progress', '-v', gitpath, cwd])._run()
            self.__git_update_metadata = False
            #repo = git.Repo.clone_from(self.git, cwd, GitProgress(), config=config, quiet=True,branch=self.branch)
            # if self.commit:
            #     repo.head.reset(commit=self.commit, index=True, working_tree=True)
        except git.exc.InvalidGitRepositoryError as e:
            assert e.status == 0, '%s\nInvalid Git Repository' % e

    def __init__(self, gitpath: str, cwd: str, branch: str='HEAD') -> None:
        ''' Precedence: commit > tag '''
        self.__git_update_metadata = True

        if not GitUtil.is_git(cwd=cwd):
            self.__clone(gitpath, branch, cwd)

        __repo = git.Repo(path=cwd)
        if __repo.remotes.origin.url != gitpath:
            shutil.rmtree(__repo.working_dir, ignore_errors=True)
            self.__clone(gitpath, branch, cwd)
            __repo = git.Repo(path=cwd)

        self.repo = __repo
        self.origin = self.repo.remotes.origin
        # get remote branch name, ready for local branch use
        self.local_branch_name = self.__get_remote_branch_name(branch)

    def __lsremote_head(self, url):
        g = git.cmd.Git()
        ref = itertools.takewhile(lambda x: x.find('\tHEAD') >= 0, g.ls_remote(url).split('\n'))
        return list(ref)[0].split('\t')[0]

    @property
    def is_outdated(self) -> bool:
        try:
            _head = self.repo.heads[self.local_branch_name]
            remote_head_commit = self.__lsremote_head(self.origin.url)
            local_head_commit = str(_head.commit)
            return remote_head_commit != local_head_commit
            #return self.origin.refs.HEAD.commit != _head.commit
        except (git.exc.GitCommandError, KeyError):
            return False

    def checkout(self, commit: str=None, tag: str=None,
                 submodule: bool=False, update_metadata: bool=False) -> None:
        try:
            _head = self.repo.heads[self.local_branch_name]
        except KeyError:
            # create local branch from remote
            #_head = repo.create_head(local_branch_name, resolved_remote_branch)
            _head = self.repo.create_head(self.local_branch_name)
            _head.set_tracking_branch(self.origin.refs[self.local_branch_name])
            _head.checkout()

        if submodule:
            Command('git submodule update --init --recursive', cwd=self.repo.working_dir)._run()
            # for submod in self.repo.submodules:
            #     # HACK: sometimes fetching submodules does not work
            #     while True:
            #         try:
            #             submod.update(init=True, recursive=True, progress=GitProgress)
            #             break
            #         except:
            #             time.sleep(2)
        #if self.commit is None:
        #    self.commit = _head.commit
        if update_metadata or self.__git_update_metadata:
            # git fetch: updates objects and refs
            #for fetch_info in self.origin.fetch(self.local_branch_name, progress=GitProgress, prune=True):
            #for fetch_info in self.origin.fetch(progress=GitProgress):
            #    logging.debug('Updated %s to %s' % (fetch_info.ref, fetch_info.commit))
            #self.repo.git.fetch('--all')
            Command('git fetch --all --progress', cwd=self.repo.working_dir)._run()

        #print(self.repo.refs['%s/%s' % (self.origin, self.local_branch_name)].commit)

        ct = self.local_branch_name
        reset = '%s/%s' % (self.origin, self.local_branch_name)

        if commit:
            try:
                # valid commit ?
                ct = list(self.repo.iter_commits(rev=commit, max_count=1))[0]
                reset = ct
            except:
                logging.debug('Commit [%s] is bad, point to %s/HEAD' % (commit, self.origin))
        elif tag:
            assert tag in self.repo.tags, 'Tag [%s] is not in repository [%s]' % (tag, self.origin.url)
            #ct = self.repo.tags[self.tag].commit
            ct = tag
            reset = ct
        commit = ct

        # if not self.repo.active_branch == _head:
        # tag_id = choose_tag()
        # self.repo.tags[tag_id]
        # _head = tag_id
        self.repo.head.set_reference(_head)
        # Resets the index and working tree. Any changes to tracked files in the working tree since <commit> are discarded.
        self.repo.head.reset(commit=reset, index=True, working_tree=True)
        assert not self.repo.head.is_detached, 'Head is detached'
        self.__clean_untracked()

        #self.commit = '%s/%s' % (self.origin, self.local_branch_name)
            #commit = '%s/%s' % (self.repo.remotes.origin, self.local_branch_name)
        try:
            self.origin.pull(commit, progress=GitProgress)

        #Command(['git', 'pull', '--progress', '-v'])._run()
        except git.exc.GitCommandError as e:
            assert e.status == 0, '%s\nProbably there are git merge conflicts.\nIs the commit [%s] is diveraged from the branch [%s]?' % (e, commit, self.local_branch_name)

        #    pass
        #print(list(self.repo.remotes))
        #self.repo.remotes.origin.pull(self.origin.refs[0].remote_head)
        #Command(['git','pull','--progress'])
        # with progress(self.repo.active_branch) as p:
        #    self.repo.remotes.origin.pull(self.local_branch_name, progress=GitProgress())
        #self.repo.remotes.origin.pull()
        #Command(['git', 'pull', '--progress', '-v', str(self.repo.remotes.origin),
        #         self.local_branch_name])._runcwd=self.repo.working_dir)

# http://stackoverflow.com/questions/33364070/python-implementing-singleton-as-metaclass-but-for-abstract-classes



# class GitRemoteProgressBar():
#     def __init__(self, library:str) -> None:
#         #self.git_clone_msg = progressbar.FormatCustomText('%(msg)s', mapping={'msg': ''})
#         self.pbar = progressbar.ProgressBar(max_value=1
#             )
#         #
#             #widgets=[library, ': ', progressbar.Percentage(), ' ',
#             #        progressbar.Bar(marker='#', left='[', right=']'), ' ', self.git_clone_msg],
#             #max_value=1)
#     def start(self) -> 'GitRemoteProgressBar':
#         logging.debug('Progress starts')
#         self.pbar.start()
#         return self
#     def finish(self) -> None:
#         logging.debug('Progress ends')
#         self.pbar.finish()
#     def update(self, op_code:Union[int,str], cur_count:int, max_count:int=None, message:str='') -> bool:
#         def is_ops(ops:git.RemoteProgress) -> bool:
#             if type(op_code) is int and type(ops) is int: return (op_code & ops) != 0
#             if type(op_code) is str and type(ops) is str: return op_code == ops
#             return False
#         def log(ops_name:str, message:str) -> None:
#             pass
#         #logging.debug('{ops_name: %s, cur_count: %s, max_count: %s, message: %s}' % (op_code, cur_count, max_count, message))
#         if is_ops(git.RemoteProgress.RECEIVING):
#             steps = cur_count / max_count
#             self.pbar.update(steps)
#             #self.git_clone_msg.update_mapping(msg=message)
#             #print('%s %s' % (cur_count, max_count))
#             time.sleep(0.05)
#         else:
#             if is_ops(git.RemoteProgress.BEGIN): log('BEGIN', message)
#             if is_ops(git.RemoteProgress.CHECKING_OUT): log('CHECKING_OUT', message)
#             if is_ops(git.RemoteProgress.COMPRESSING): log('COMPRESSING', message)
#             if is_ops(git.RemoteProgress.COUNTING): log('COUNTING', message)
#             if is_ops(git.RemoteProgress.DONE_TOKEN): log('DONE_TOKEN', message)
#             if is_ops(git.RemoteProgress.END): log('END', message)
#             if is_ops(git.RemoteProgress.FINDING_SOURCES): log('FINDING_SOURCES', message)
#             if is_ops(git.RemoteProgress.OP_MASK): log('OP_MASK', message)
#             if is_ops(git.RemoteProgress.RESOLVING): log('RESOLVING', message)
#             if is_ops(git.RemoteProgress.STAGE_MASK): log('STAGE_MASK', message)
#             if is_ops(git.RemoteProgress.WRITING): log('WRITING', message)
#
# @contextmanager
# def progress(library:str) -> Iterator[GitRemoteProgressBar]:
#     try:
#         p = GitRemoteProgressBar(library).start()
#         yield p
#     finally:
#         p.finish()
#print_lock = threading.RLock()
# def save_print(*args, **kwargs):
 # with print_lock:
#    print (*args, **kwargs)
