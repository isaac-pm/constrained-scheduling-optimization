% =============================================================================
% PROBLEM INPUTS (Parameters)
% These are the known details about our project that we feed into the model.
% =============================================================================

int: n;                                 % The total number of activities in the project
int: horizon;                           % The absolute maximum time the project could possibly take
int: num_resources;                     % Number of renewable resources in the instance
array[1..n] of int: duration;           % How many time units each activity takes to complete
array[1..n, 1..num_resources] of int: resource_usage; % Resource usage per activity and resource
array[1..num_resources] of int: capacity; % The maximum amount of each resource available at any given time
array[1..n] of set of int: successors;  % For each activity, a list of other activities that must wait for it to finish

% =============================================================================
% DERIVED BOUNDS (EST/LST) AND REACHABILITY
% =============================================================================

array[1..n] of set of int: predecessors = [ {i | i in 1..n where j in successors[i]} | j in 1..n ];

function int: est_fun(int: j) =
    if card(predecessors[j]) = 0 then
        0
    else
        max(i in predecessors[j])(est_fun(i) + duration[i])
    endif;

array[1..n] of int: est = [ est_fun(j) | j in 1..n ];
int: cpm_lb = max(j in 1..n)(est[j] + duration[j]);

function int: lst_fun(int: j) =
    if card(successors[j]) = 0 then
        horizon - duration[j]
    else
        min(s in successors[j])(lst_fun(s) - duration[j])
    endif;

array[1..n] of int: lst = [ lst_fun(j) | j in 1..n ];

function bool: reach_fun(int: i, int: j) =
    if j in successors[i] then
        true
    else
        exists(s in successors[i])(reach_fun(s, j))
    endif;

array[1..n, 1..n] of bool: reachable =
    array2d(1..n, 1..n, [ reach_fun(i, j) | i in 1..n, j in 1..n ]);

% =============================================================================
% DECISION VARIABLES
% These are the blanks the solver needs to fill in to create the schedule.
% =============================================================================

% We need to find a specific start time for every activity.
% The start time can be anywhere from its earliest to latest feasible bound.
array[1..n] of var int: start = [let {var est[j]..lst[j]: sj} in sj | j in 1..n];

% We need to find the overall finish time of the entire project.
var 0..horizon: makespan;

% =============================================================================
% RULES (Constraints)
% The conditions that must be met for a schedule to be valid.
% =============================================================================

% RULE 1: Stay within the time limit.
% For every activity, its start time plus how long it takes (its finish time)
% must not exceed our absolute maximum time horizon.
constraint
    forall(j in 1..n) (
        start[j] + duration[j] <= horizon + 1
    );


% RULE 2: Respect the order of operations.
% For every activity, look at all the activities that are supposed to come after it (successors).
% The successor's start time must be greater than or equal to the current activity's finish time.
constraint
    forall(j in 1..n, s in successors[j]) (
        start[j] + duration[j] <= start[s]
    );

% RULE 2b: Transitive precedence (redundant but strengthens propagation).
constraint
    forall(i in 1..n, j in 1..n where i != j /\ reachable[i, j] /\ not (j in successors[i])) (
        start[i] + duration[i] <= start[j]
    );

% RULE 3: Define the final project end time.
% The overall end time of the project (makespan) is simply the finish time 
% (start time + duration) of whichever activity finishes the very last.
constraint
    makespan = max(j in 1..n)(start[j] + duration[j]);

% RULE 3b: Critical-path lower bound.
constraint
    makespan >= cpm_lb;

% RULE 4: Do not run out of resources.
% Use MiniZinc's scheduling globals for cumulative resource usage.
include "globals.mzn";
constraint
    forall(r in 1..num_resources) (
        cumulative(
            start,
            duration,
            [resource_usage[j, r] | j in 1..n],
            capacity[r]
        )
    );

% =============================================================================
% GOAL
% =============================================================================
% Find a valid schedule that makes the final end time (makespan) as small as possible.
solve
  :: seq_search([
       int_search(start, first_fail, indomain_min, complete),
       int_search([makespan], input_order, indomain_min, complete)
     ])
  minimize makespan;
