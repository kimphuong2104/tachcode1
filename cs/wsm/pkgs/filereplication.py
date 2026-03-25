#!/usr/bin/env python
# -*- python -*- coding: iso-8859-1 -*-
#
# Copyright (C) 1990 - 2017 CONTACT Software GmbH
# All rights reserved.
# http://www.contact.de/
#
from __future__ import absolute_import
import logging

from cdb.objects.cdb_file import _get_blobstore as get_blobstore
from cdb.storage.exceptions import ConnectionError
from cs.wsm.pkgs.pkgsutils import grouper
from cdb.storage.replication import BlobStates

# 1000 is a reasonable size (so says platform team)
BLOBS_PER_REPL_GROUP = 1000
REMOTE_STATES = (
    BlobStates.BLOB_STATE_REMOTE,
    BlobStates.BLOB_STATE_GETTING,
    BlobStates.BLOB_STATE_UNKNOWN,
)


class FileReplication(object):
    """
    Manages blob replication and replication cleanup for a user session.
    """

    def __init__(self, user, mac_address, windows_session_id):
        self.ordererId = u"WSM-%s-%s-%s" % (user, mac_address, windows_session_id)
        self.bs = get_blobstore("main")
        logging.info("WSM REPL blobstore: %s", self.bs)

    def trigger(self, blobIds):
        prioBlobs = None
        logging.info("WSM REPL total num blobs: %s", len(blobIds))
        # quit already running replications, e.g. after user cancel
        self.cleanUp()
        logging.info("WSM REPL starting with orderer: %s", self.ordererId)
        remoteBlobsExists = False
        localBlobs = set()
        try:
            for blobIdsChunk in grouper(BLOBS_PER_REPL_GROUP, blobIds):
                blobIdsChunk = list(blobIdsChunk)
                rg = self.bs.ReplicationGroup(blobIdsChunk)
                if rg:
                    logging.info(
                        "WSM REPL starting replication for %s blobs", len(blobIdsChunk)
                    )
                    rg.start(self.ordererId)

                    logging.info("WSM REPL checking blob replication states")
                    for replStatus in rg.status():
                        if replStatus.state != BlobStates.BLOB_STATE_LOCAL:
                            localBlobs.add(replStatus.blob_id)
                        elif replStatus.state in REMOTE_STATES:
                            remoteBlobsExists = True
                else:
                    logging.info("WSM REPL no replication necessary for current chunk")
                    localBlobs.update(blobIdsChunk)
        except ConnectionError:
            logging.exception("WSM REPL trigger: failed with exception")

        # if there is nothing to replicate we dont need to prioritize
        if remoteBlobsExists and localBlobs:
            prioBlobs = localBlobs
        return prioBlobs

    def cleanUp(self):
        """
        Closes all running replications for specific ordererId

        Final replication cleanUp must be done after all files have
        been transferred, e.g. in PostBlobDownProcessor.

        Worst case, if ReplicationGroup.finalize never happens:
        obsolete entries in replication db. They will be deleted after 2 weeks.
        """
        try:
            groups = self.bs.ReplicationGroup(orderer_id=self.ordererId)
            logging.info(
                "WSM REPL cleanUp: orderer %s, num groups %s",
                self.ordererId,
                len(groups),
            )
            for group in groups:
                group.finalize()
        except ConnectionError:
            logging.exception("WSM REPL cleanUp: failed with exception")
