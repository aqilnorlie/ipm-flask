
$( document ).ready(function() {
    
    $(".alert").hide() // Hide div
    $("#retype_password").on("input",function(){

        let password = $("#password").val()
        let retype = $("#retype_password").val()
        let btn = ""
        
        if(password != retype){
            $("#icon_change").replaceWith("<span id= 'icon_change' class= 'fa fa-times'></span>")
            btn += "<button type='submit' id='btn_register' class='btn btn-danger btn-block' disabled>Please Retype Same Password</button> "
            $("#div_register").html(btn)

        }else{
            $("#icon_change").replaceWith("<span id= 'icon_change' class= 'fa fa-check'></span>")
            btn += "<button type='submit' id='btn_register' class='btn btn-success btn-block'>Register</button> "
            $("#div_register").html(btn)
        }

    })

    

    

   
    
});