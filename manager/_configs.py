#: When nodes are removed from the fleet, they are labeled with a terminating
#: state label. These are used to identify when a node is ready to be
#: terminated by the shrink fleet step and introduces a bit of lag between
#: identifying a node for termination and then actually terminating it. This
#: allows for a more graceful termination period inside kubernetes where pods
#: can be evicted by taints instead of just terminating the instances
#: immediately and potentially orphaning pods.
STATE_KEY = "fleet-manager-state"
ACTIVE_STATE = "active"
TERMINATING_STATE = "terminating"
WARMING_UP_STATE = "warming_up"
SHUTTING_DOWN_STATE = "shutting_down"
