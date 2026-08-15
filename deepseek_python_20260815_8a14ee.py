# example.py
# English example file that uses the quantum circuit functions
# This file imports and demonstrates the usage of the quantum circuits
# without modifying the original code

from from qiskit import QuantumCircuit, transpile import (
    dibujar_circuito_texto,
    ejecutar_simulacion,
    circuito_bell,
    circuito_ghz,
    circuito_superposicion,
    dibujar_circuito,
    ejecutar_circuito,
    info_circuito,
    test_conexion
)

def main():
    """Main function to demonstrate all quantum circuit functionality"""
    
    print("=" * 60)
    print("QUANTUM CIRCUIT DEMONSTRATION")
    print("=" * 60)
    
    # Test connection
    print("\n1. Testing connection:")
    print(test_conexion())
    
    # Display circuit information for each type
    print("\n2. Circuit Information:")
    print("-" * 40)
    
    for circuit_type in ["bell", "ghz", "superposicion"]:
        print(f"\n{circuit_type.upper()} CIRCUIT:")
        print(info_circuito(circuit_type))
    
    # Draw each circuit
    print("\n3. Circuit Diagrams:")
    print("-" * 40)
    
    for circuit_type in ["bell", "ghz", "superposicion"]:
        print(f"\n{circuit_type.upper()} Circuit:")
        print(dibujar_circuito(circuit_type))
    
    # Execute each circuit
    print("\n4. Circuit Execution Results:")
    print("-" * 40)
    
    for circuit_type in ["bell", "ghz", "superposicion"]:
        print(f"\nExecuting {circuit_type.upper()} circuit...")
        result = ejecutar_circuito(circuit_type, shots=1024)
        print(result)
    
    # Execute with different number of shots
    print("\n5. Execution with different shots:")
    print("-" * 40)
    
    print("\nExecuting Bell circuit with 500 shots:")
    result = ejecutar_circuito("bell", shots=500)
    print(result)
    
    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()