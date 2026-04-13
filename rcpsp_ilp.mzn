int: n;
int: horizon;
array[1..n] of int: duration;
array[1..n, 1..4] of int: resource_usage;
array[1..4] of int: capacity;
array[1..n] of set of int: successors;

array[1..n, 0..horizon] of var 0..1: x;

var 0..horizon: makespan;

constraint
    forall(j in 1..n) (
        sum(t in 0..horizon)(x[j, t]) = 1
    );

constraint
    forall(j in 1..n) (
        sum(t in 0..horizon)(t * x[j, t]) + duration[j] <= horizon + 1
    );

constraint
    forall(j in 1..n, s in successors[j]) (
        sum(t in 0..horizon)(t * x[j, t]) + duration[j] <= sum(t in 0..horizon)(t * x[s, t])
    );

constraint
    forall(j in 1..n)(
        makespan >= sum(t in 0..horizon)(t * x[j, t]) + duration[j]
    );

constraint
    forall(r in 1..4) (
        forall(t in 0..horizon) (
            sum(j in 1..n)(
                resource_usage[j, r] * sum(tt in max(0, t-duration[j]+1)..t)(x[j, tt])
            ) <= capacity[r]
        )
    );

solve minimize makespan;