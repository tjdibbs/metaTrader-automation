import MetaTrader5 as mt5


# Function to start MetaTrader
def start_mt5(**kwargs):

    print("Intializing MetaTrader...")

    started = False

    try:
        # if mt5.initialize():
        #     print(kwargs)
        #     authorized = mt5.login(**kwargs)

        #     if not authorized: print("Not authorized. Are you sure the creditials are correct ?")
        #     else: started = authorized
        started = mt5.initialize()

    except Exception as e:
        print(f"An Error occurred While Starting MetaTrader {e}")

    return started