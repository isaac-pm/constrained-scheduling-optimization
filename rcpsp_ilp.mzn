% =============================================================================
% PROBLEM INPUTS (Parameters)
% (These are identical to the CP model)
% =============================================================================

int: n;
int: horizon;
int: num_resources;
array[1..n] of int: duration;
array[1..n, 1..num_resources] of int: resource_usage;
array[1..num_resources] of int: capacity;
array[1..n] of set of int: successors;

% =============================================================================
% DERIVED BOUNDS (EST/LST)
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

int: ub = max(j in 1..n)(lst[j] + duration[j]);

% =============================================================================
% DECISION VARIABLES
% Because ILP relies on linear math, we can't just pick a "start time" number.
% Instead, we create a massive grid of yes/no switches.
% =============================================================================

% For every activity (1 to n), and for every possible moment in time (0 to horizon),
% we have a variable that can only be 0 (no) or 1 (yes).
% A '1' means "This activity starts exactly at this specific time."
array[1..n, 0..horizon] of var 0..1: x;

% The overall end time of the project.
var cpm_lb..ub: makespan;

% =============================================================================
% RULES (Constraints)
% =============================================================================

% RULE 1: Every activity must happen.
% For each activity, if we add up all its yes/no switches across the entire timeline,
% the total must be exactly 1. This forces the activity to start exactly once.
constraint
    forall(j in 1..n) (
        sum(t in est[j]..lst[j])(x[j, t]) = 1
    );

% RULE 1b: Fix out-of-window binaries.
constraint
    forall(j in 1..n, t in 0..horizon) (
        if t < est[j] \/ t > lst[j] then x[j, t] = 0 else true endif
    );

% RULE 3: Respect the order of operations (Strong LP Step Formulation)
constraint
    forall(j in 1..n, s in successors[j]) (
        forall(t in est[s]..lst[s]) (
            sum(tau in est[s]..t)(x[s, tau])
            <=
            sum(tau in est[j]..min(t - duration[j], lst[j]))(x[j, tau])
        )
    );

% RULE 4: Define the final project end time (Optimized for PSPLIB)
% Node 'n' is the dummy sink. Its start time is the exact makespan.
constraint
    makespan = sum(t in est[n]..lst[n])(t * x[n, t]);

% RULE 5: Do not run out of resources (Sparse formulation)
constraint
    forall(r in 1..num_resources) (
        forall(t in 0..horizon) (
            sum(j in 1..n where resource_usage[j, r] > 0)(
                resource_usage[j, r] *
                sum(tt in max(0, t-duration[j]+1)..t)(x[j, tt])
            ) <= capacity[r]
        )
    );
% =============================================================================
% GOAL
% =============================================================================
% Push the final end time variable to be as small as structurally possible.
solve minimize makespan;
