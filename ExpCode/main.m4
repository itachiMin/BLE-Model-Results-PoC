/*
changequote(<!,!>)dnl
Initiator Host:
  ifdef(<!IDisplayOnly!>, DisplayOnly, 
    ifdef(<!IDisplayYesNo!>, DisplayYesNo, 
    ifdef(<!IKeyboardOnly!>, KeyboardOnly,
    ifdef(<!INoInputNoOutput!>, NoInputNoOutput,
    ifdef(<!IKeyboardDisplay!>, KeyboardDisplay))))) dnl

  ifdef(<!IOOBSendRev!>, OOBSendRev,
    ifdef(<!IOOBSend!>, OOBSend,
    ifdef(<!IOOBRev!>, OOBRev,
    ifdef(<!INoOOB!>, NoOOB)))) dnl

  ifdef(<!IAuthReq!>, AuthReq, 
    ifdef(<!INoAuthReq!>, NoAuthReq)) dnl

  ifdef(<!IKeyHigh!>, <!KeyHigh!>,
    ifdef(<!IKeyLow!>, <!KeyLow!>))
Responder Host:
  ifdef(<!RDisplayOnly!>, DisplayOnly, 
    ifdef(<!RDisplayYesNo!>, DisplayYesNo, 
    ifdef(<!RKeyboardOnly!>, KeyboardOnly,
    ifdef(<!RNoInputNoOutput!>, NoInputNoOutput,
    ifdef(<!RKeyboardDisplay!>, KeyboardDisplay))))) dnl

  ifdef(<!ROOBSendRev!>, OOBSendRev,
    ifdef(<!ROOBSend!>, OOBSend,
    ifdef(<!ROOBRev!>, OBRev,
    ifdef(<!RNoOOB!>, NoOOB)))) dnl

  ifdef(<!RAuthReq!>, AuthReq, 
    ifdef(<!RNoAuthReq!>, NoAuthReq)) dnl

  ifdef(<!RKeyHigh!>, KeyHigh,
    ifdef(<!RKeyLow!>, KeyLow)) changequote
*/ 
theory BLE_SC_Host_HCI_Controller_Model
begin

include(includes/header.m4i)

include(includes/tactic.m4i)

include(includes/predicates.m4i)

dnl/*
dnl* ****************************************************************
dnl*                   Communication Channel                   
dnl* ****************************************************************
dnl*/ 
include(includes/channels.m4i)

dnl/*
dnl* ****************************************************************
dnl*                       Initialization                    
dnl* ****************************************************************
dnl*/ 
include(includes/initConnection.m4i)

dnl/*
dnl* ****************************************************************
dnl*                       User's Behaviours                   
dnl* ****************************************************************
dnl*/ 
include(includes/user.m4i)

dnl/*
dnl* ****************************************************************
dnl*                      Modeling Controller                   
dnl* *************** Including Centeral and Peripheral **************
dnl* ****************************************************************
dnl*/ 
include(includes/controller.m4i)

dnl/*
dnl* ****************************************************************
dnl*                    Modeling Initiator Host                   
dnl* ****************************************************************
dnl*/ 
include(includes/iHost.m4i)

dnl/*
dnl* ****************************************************************
dnl*                    Modeling Responder Host                   
dnl* ****************************************************************
dnl*/ 
include(includes/rHost.m4i)

dnl/*
dnl* ****************************************************************
dnl*                         Restrictions                   
dnl* ****************************************************************
dnl*/ 
include(includes/restrictions.m4i)

dnl/*
dnl* ****************************************************************
dnl*                            Lemmas                   
dnl* ****************************************************************
dnl*/ 
include(includes/lemmas.m4i)

end