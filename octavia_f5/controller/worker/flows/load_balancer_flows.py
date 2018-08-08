# Copyright 2018 SAP SE
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_config import cfg
from oslo_log import log as logging
from taskflow.patterns import linear_flow

from octavia.controller.worker.tasks import database_tasks
from octavia.controller.worker.tasks import lifecycle_tasks
from octavia_f5.common import constants
from octavia_f5.controller.worker.tasks import f5_driver_tasks

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

class LoadBalancerFlows(object):
    def get_create_load_balancer_flow(self):
        """
        :return: The graph flow for creating a loadbalancer.
        """

        f_name = constants.CREATE_LOADBALANCER_FLOW
        lb_create_flow = linear_flow.Flow(f_name)

        lb_create_flow.add(lifecycle_tasks.LoadBalancerToErrorOnRevertTask(
            requires=constants.LOADBALANCER))

        lb_create_flow.add(f5_driver_tasks.EnsurePartitionCreated(
            requires=(constants.LOADBALANCER, constants.BIGIP)))
        lb_create_flow.add(f5_driver_tasks.DeletePartition(
            requires=(constants.LOADBALANCER, constants.BIGIP)))
        lb_create_flow.add(database_tasks.MarkLBActiveInDB(
            name= 'some-flow-' + constants.MARK_LB_ACTIVE_INDB,
            requires=constants.LOADBALANCER))

        return lb_create_flow

    def get_delete_load_balancer_flow(self, lb):
        """Creates a flow to delete a load balancer.

        :returns: The flow for deleting a load balancer
        """
        # (listeners_delete, store) = self._get_delete_listeners_flow(lb)
        store = {}

        delete_LB_flow = linear_flow.Flow(constants.DELETE_LOADBALANCER_FLOW)
        delete_LB_flow.add(lifecycle_tasks.LoadBalancerToErrorOnRevertTask(
            requires=constants.LOADBALANCER))
        #delete_LB_flow.add(listeners_delete)
        #delete_LB_flow.add(network_tasks.UnplugVIP(
        #    requires=constants.LOADBALANCER))
        #delete_LB_flow.add(network_tasks.DeallocateVIP(
        #    requires=constants.LOADBALANCER))
        delete_LB_flow.add(database_tasks.MarkLBDeletedInDB(
            requires=constants.LOADBALANCER))
        delete_LB_flow.add(database_tasks.DecrementLoadBalancerQuota(
            requires=constants.LOADBALANCER))

        return delete_LB_flow, store


    def get_cascade_delete_load_balancer_flow(self, lb):
        """Creates a flow to delete a load balancer.

        :returns: The flow for deleting a load balancer
        """

        #(listeners_delete, store) = self._get_delete_listeners_flow(lb)
        #(pools_delete, pool_store) = self._get_delete_pools_flow(lb)
        #store.update(pool_store)
        store = {}

        delete_LB_flow = linear_flow.Flow(constants.DELETE_LOADBALANCER_FLOW)
        delete_LB_flow.add(lifecycle_tasks.LoadBalancerToErrorOnRevertTask(
            requires=constants.LOADBALANCER))
        #delete_LB_flow.add(pools_delete)
        #delete_LB_flow.add(listeners_delete)
        #delete_LB_flow.add(network_tasks.UnplugVIP(
        #    requires=constants.LOADBALANCER))
        #delete_LB_flow.add(network_tasks.DeallocateVIP(
        #    requires=constants.LOADBALANCER))
        delete_LB_flow.add(f5_driver_tasks.DeletePartition(
            requires=(constants.LOADBALANCER, constants.BIGIP)))
        delete_LB_flow.add(database_tasks.MarkLBDeletedInDB(
            requires=constants.LOADBALANCER))
        delete_LB_flow.add(database_tasks.DecrementLoadBalancerQuota(
            requires=constants.LOADBALANCER))

        return delete_LB_flow, store
