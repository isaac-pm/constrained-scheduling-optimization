int: n;
int: horizon;
array[1..n] of int: duration;
array[1..n, 1..4] of int: resource_usage;
array[1..4] of int: capacity;
array[1..n] of set of int: successors;

array[1..n] of var 0..horizon: start;
var 0..horizon: makespan;

constraint
    forall(j in 1..n) (
        start[j] + duration[j] <= horizon + 1
    );

constraint
    forall(j in 1..n, s in successors[j]) (
        start[j] + duration[j] <= start[s]
    );

constraint
    makespan = max(j in 1..n)(start[j] + duration[j]);

constraint
    forall(r in 1..4) (
        forall(t in 0..horizon) (
            sum(j in 1..n where start[j] <= t /\ start[j] + duration[j] > t)(
                resource_usage[j, r]
            ) <= capacity[r]
        )
    );

solve minimize makespan;
