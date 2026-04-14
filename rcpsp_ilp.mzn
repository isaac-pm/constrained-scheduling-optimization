% =============================================================================
% PROBLEM INPUTS (Parameters)
% (These are identical to the CP model)
% =============================================================================

int: n;
int: horizon;
array[1..n] of int: duration;
array[1..n, 1..4] of int: resource_usage;
array[1..4] of int: capacity;
array[1..n] of set of int: successors;

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
var 0..horizon: makespan;

% =============================================================================
% RULES (Constraints)
% =============================================================================

% RULE 1: Every activity must happen.
% For each activity, if we add up all its yes/no switches across the entire timeline,
% the total must be exactly 1. This forces the activity to start exactly once.
constraint
    forall(j in 1..n) (
        sum(t in 0..horizon)(x[j, t]) = 1
    );

% RULE 2: Stay within the time limit.
% For each activity, we calculate its actual start time by multiplying the time slot 't' 
% by its yes/no switch. (Since only one switch is 1, all others become 0).
% We then add its duration. The result must fit within the horizon.
constraint
    forall(j in 1..n) (
        sum(t in 0..horizon)(t * x[j, t]) + duration[j] <= horizon + 1
    );

% RULE 3: Respect the order of operations.
% Just like Rule 2, we calculate the finish time of an activity.
% We then calculate the start time of its successor using the same trick.
% The finish time of the first must be less than or equal to the start time of the second.
constraint
    forall(j in 1..n, s in successors[j]) (
        sum(t in 0..horizon)(t * x[j, t]) + duration[j] <= sum(t in 0..horizon)(t * x[s, t])
    );

% RULE 4: Define the final project end time (Linearized).
% Since ILP struggles with the "max()" function, we do this differently.
% We state that the project's overall end time must be greater than or equal to 
% the finish time of EVERY single activity. 
% When the solver tries to minimize the makespan, it will push this number down 
% until it hits the finish time of the very last activity.
constraint
    forall(j in 1..n)(
        makespan >= sum(t in 0..horizon)(t * x[j, t]) + duration[j]
    );

% RULE 5: Do not run out of resources.
% We check every single resource, at every single moment in time.
constraint
    forall(r in 1..4) (
        forall(t in 0..horizon) (
            % To figure out if an activity is running at time 't', we look backwards.
            % We check the time slots just before 't' to see if the activity started 
            % recently enough that it would still be going on right now.
            sum(j in 1..n)(
                resource_usage[j, r] * % Add up the yes/no switches for the start times that would overlap with 't'.
                % If it started in this window, this sum is 1, so we add its resource usage.
                % If it didn't, the sum is 0, so it uses 0 resources.
                sum(tt in max(0, t-duration[j]+1)..t)(x[j, tt])
            ) <= capacity[r] % The total cannot exceed what is available.
        )
    );

% =============================================================================
% GOAL
% =============================================================================
% Push the final end time variable to be as small as structurally possible.
solve minimize makespan;