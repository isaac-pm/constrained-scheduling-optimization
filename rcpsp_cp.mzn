% =============================================================================
% PROBLEM INPUTS (Parameters)
% These are the known details about our project that we feed into the model.
% =============================================================================

int: n;                                 % The total number of activities in the project
int: horizon;                           % The absolute maximum time the project could possibly take
array[1..n] of int: duration;           % How many time units each activity takes to complete
array[1..n, 1..4] of int: resource_usage; % How much of each of the 4 resources an activity needs while running, TODO update amount of resources to be dynamic and match each problem instance
array[1..4] of int: capacity;           % The maximum amount of each resource available at any given time
array[1..n] of set of int: successors;  % For each activity, a list of other activities that must wait for it to finish

% =============================================================================
% DECISION VARIABLES
% These are the blanks the solver needs to fill in to create the schedule.
% =============================================================================

% We need to find a specific start time for every activity.
% The start time can be anywhere from 0 up to the maximum horizon limit.
array[1..n] of var 0..horizon: start;

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

% RULE 3: Define the final project end time.
% The overall end time of the project (makespan) is simply the finish time 
% (start time + duration) of whichever activity finishes the very last.
constraint
    makespan = max(j in 1..n)(start[j] + duration[j]);

% RULE 4: Do not run out of resources.
% We check every single resource, at every single moment in time.
constraint
    forall(r in 1..4) (
        forall(t in 0..horizon) (
            % At time 't', find all activities that have already started but haven't finished yet.
            % Sum up how much of the resource they are currently using.
            sum(j in 1..n where start[j] <= t /\ start[j] + duration[j] > t)(
                resource_usage[j, r]
            ) <= capacity[r] % This total sum cannot be higher than what we have available.
        )
    );

% =============================================================================
% GOAL
% =============================================================================
% Find a valid schedule that makes the final end time (makespan) as small as possible.
solve minimize makespan;

% TODO Implement this for easier scheduling: https://docs.minizinc.dev/en/stable/lib-globals-scheduling.html