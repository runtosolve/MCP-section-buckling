using CeeSectionBucklingAPI: perform_calculation
using JSON3

# 复刻 Chu Ding 反馈的 case
# H=6, B=1.25, t=0.054, L=0.5, r=0.135, units=inch
# 注意: 当前 mcp-server.py 不做单位转换, 所以 Julia 拿到的就是这些数字
inputs = (
    E = 29500.0,    # ksi (as if inch mode; without conversion backend treats as MPa)
    ν = 0.3,
    t = 0.054,
    L = 0.5,
    B = 1.25,
    H = 6.0,
    r = 0.135,
)

inputs_path  = tempname() * ".json"
outputs_path = tempname() * ".json"
open(inputs_path, "w") do f
    JSON3.write(f, inputs)
end

perform_calculation(inputs_path, outputs_path)

result = JSON3.read(read(outputs_path, String))

println("─── Pcrl / Pcrd ───")
println("Pcrℓ = ", result.Pcrℓ)
println("Pcrd = ", result.Pcrd)

if hasproperty(result, :local_buckling_mode_shape)
    ms = result.local_buckling_mode_shape
    X = ms.X  # Vector{Vector{Float64}}
    Y = ms.Y

    all_x = reduce(vcat, X)
    all_y = reduce(vcat, Y)

    println("\n─── Local buckling mode shape bounds ───")
    println("X range: [", minimum(all_x), ", ", maximum(all_x), "]  (input B = ", inputs.B, ")")
    println("Y range: [", minimum(all_y), ", ", maximum(all_y), "]  (input H = ", inputs.H, ")")
    println("# of strips: ", length(X))

    # 判断是全截面还是半截面
    expected_x_span = inputs.B
    expected_y_span = inputs.H
    actual_x_span = maximum(all_x) - minimum(all_x)
    actual_y_span = maximum(all_y) - minimum(all_y)
    println("\nX span ratio (actual/expected): ", round(actual_x_span/expected_x_span, digits=3))
    println("Y span ratio (actual/expected): ", round(actual_y_span/expected_y_span, digits=3))
end

cp(outputs_path, joinpath(@__DIR__, "mode_shapes.json"), force=true)
println("\n→ Mode shape data saved to mode_shapes.json")

rm(inputs_path, force=true)
rm(outputs_path, force=true)
