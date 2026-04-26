document.addEventListener("DOMContentLoaded", function() {
    // Seleccionamos los inputs por su atributo 'name'
    // Agrega 'username' si quieres que también funcione en el login (cuidado con el usuario 'admin')
    var rutInputs = document.querySelectorAll('input[name="rut"], input[name="rut_consulta"]');
    
    rutInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            // Limpiar el valor dejando solo números y K
            var valor = this.value.replace(/[^0-9kK]/g, "").toUpperCase();
            
            if (valor.length > 1) {
                var cuerpo = valor.slice(0, -1);
                var dv = valor.slice(-1);
                
                // Formatear el cuerpo con puntos y agregar el guión y DV
                this.value = cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "-" + dv;
            } else {
                this.value = valor;
            }
        });
    });
});