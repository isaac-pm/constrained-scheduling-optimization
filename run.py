from psplib import parse

instance = parse("data/j30.sm/j301_1.sm", instance_format="psplib")
print(instance.num_resources)
print(instance.num_activities)
print(instance.activities)

# from minizinc import Instance, Model, Solver

# # Load n-Queens model from file
# model = Model("./model.mzn")
# # Find the MiniZinc solver configuration for Gecode
# gecode = Solver.lookup("gecode")
# # Create an Instance of the n-Queens model for Gecode
# instance = Instance(gecode, model)
# # Assign 4 to n
# instance["n"] = 4
# result = instance.solve()
# # Output the array q
# print(result["q"])
