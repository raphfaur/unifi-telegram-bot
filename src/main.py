from telegram.ext import ApplicationBuilder, CommandHandler, filters
from unifi import Unifi
import monitoring
from telegram.constants import ParseMode
from config import password, username, chat_id, token, trig, warn

warning = False
triggered = False

async def find_device(update, context) :
    """Find AP's mac with the arg as name

    Args:
        update (update): messsage update
        context (context): message context
    """
    name = context.args[0]
    device = unifi.find_mac_by_name(name)
    if name in unifi.downed_devices :
        answer = "Device " + name + "❌ is : " + device
    else :
        answer = "Device " + name + " ✅ is : " + device
    await update.message.reply_text(answer)


async def monitor(context) :
    """ monitor

    Args:
        context (context): message context
    """
    # This task just check the state of the monitoring values and send messages consequently
    global chat_id, monitor_thread, downed_device_list, triggered, warning
    downed_device_list, delta, lost_users = monitor_thread.get_state()
    if len(downed_device_list) >= trig and not triggered :
        await context.bot.send_message(chat_id = chat_id, text = "<a href = \"unifi.yourdomain.com\">[Triggered] " + str(len(downed_device_list)) + 
        " devices are down.\nLost " + str(lost_users) + " users. 🆘</a>", parse_mode = ParseMode.HTML )
        triggered = True
    if len(downed_device_list) >= warn and not warning:
        await context.bot.send_message(chat_id = chat_id, text = "<a href = \"unifi.yourdomain.com\" >[Warn] " + str(len(downed_device_list)) + 
        " devices are down.\nLost " + str(lost_users) + " users. ⚠️</a>", parse_mode = ParseMode.HTML )
        warning = True
    if len(downed_device_list) < warn and warning:
        await context.bot.send_message(chat_id = chat_id, text = "<a href = \"unifi.yourdomain.com\">[Recovered] " + str(len(downed_device_list)) + 
        " devices are down.\n" +str( - delta) + " recovered since last healthcheck. ✅", parse_mode = ParseMode.HTML)
        warning = False
        triggered = False
    for message in monitor_thread.get_info() :
        await context.bot.send_message(chat_id = chat_id, text = message) 

async def users(update, context) :
    """Returns number of users and last update
    """
    users_count = len(unifi.users)
    await update.message.reply_text(f"There is currently {users_count} users. \nLast update : {monitor_thread.last_update}")

async def downed_devices(update, context) :
    """List downed devices

    Args:
        update (update): chat update
        context (context): message context
    """
    message='\n'.join(['❌ '+ap for ap in unifi.downed_devices]) + f"<i>\nLast update : {monitor_thread.last_update}</i>"
    await context.bot.send_message(chat_id = chat_id, text = message, parse_mode = ParseMode.HTML)

async def restart_device(update, context) :
    """ Restart device

    Args:
        update (update): chat update
        context (context): message context
    """
    name = context.args[0]
    mac = unifi.find_mac_by_name(name)
    answer, status = unifi.restart(mac)
    await context.bot.send_message(chat_id = chat_id, text = answer + name +" on " + mac )
    if status == 1 :
        monitor_thread.watch(name)

async def get_near(context, vlan):
    """Given the vlan as arg, send a message with every near APs

    Args:
        context (context): context
        vlan (str): vlan number
    """
    ap_per_device, direct_ap = unifi.get_near_ap(vlan)
    text = ""
    for (device, accesspoints) in ap_per_device.items() :
        text += f'Near {device} :\n'
        for ap_name in accesspoints :
            if ap_name in direct_ap :
                if not ap_name in downed_device_list :
                    text += f"- <b>{ap_name} ✅\n</b>"
                else :
                    text += f"- <b>{ap_name} ❌\n</b>"
            else :
                if not ap_name in downed_device_list :
                    text += f"- {ap_name} ✅\n"
                else :
                    text += f"- {ap_name} ❌\n"
    if len(text) == 0 :
        text = "No devices found ❌"
    await context.bot.send_message(chat_id = chat_id, text = text, parse_mode = ParseMode.HTML)

async def get_near_devices(update, context) :
    """Starts the scan for near APs

    Args:
        update (update): update
        context (context): context
    """
    try:
        vlan = context.args[0]
        await context.bot.send_message(chat_id = chat_id, text = f'Starting scan near {vlan} 🔎')
    except Exception:
        await update.message.reply_text("No id specidfied...")
        return
    await get_near(context, vlan)

async def get_help(update, context) :
    """Sends the help message

    Args:
        update (update): update
        context (context): context
    """
    await context.bot.send_message(chat_id = update.message.chat_id, text =
    "/update : update list of devices \n/find deviceName : find mac address of device \n/restart deviceName : restart device \n/start : reconnect the bot to the api and refresh data \n/downed : list all devices that are downed")

async def start(update, context) :
    """Restarts the bot and launch monitoring thread

    Args:
        update (update): update
        context (context): context
    """
    global downed_device_list, monitor_thread
    await context.bot.send_message(chat_id = chat_id, text = "Wait a moment, I'm starting 🙂")
    try :
        monitor_thread.stop()
        monitor_thread.join()
        await context.bot.send_message(chat_id = chat_id, text = "Monitoring stopped.")
    except Exception:
        pass
    monitor_thread = monitoring.Monitoring(unifi)
    monitor_thread.start()
    await context.bot.send_message(chat_id = chat_id, text = "Ok, ready to go !")

if __name__ == '__main__' :
    chatfilter = filters.Chat(chat_id)
    unifi = Unifi(username, password)
    app = ApplicationBuilder().token(token).build()
    #Create handlers for commands
    start_handler = CommandHandler('start', start, filters = chatfilter)
    check_handler = CommandHandler('check', start, chatfilter)
    find_device_handler = CommandHandler('find', find_device, chatfilter)
    restart_device_handler = CommandHandler('restart', restart_device, chatfilter)
    downed_devices_handler = CommandHandler('downed', downed_devices,chatfilter)
    help_handler = CommandHandler('help', get_help,chatfilter)
    users_handler = CommandHandler('users', users,chatfilter)
    near_devices_handler = CommandHandler('nearme', get_near_devices,chatfilter)
    #Add repeating jobs
    monitor_job = app.job_queue.run_repeating(monitor, 10, 0)
    job_queue = app.job_queue
    app.add_handlers([start_handler, find_device_handler, restart_device_handler,
    help_handler, downed_devices_handler, near_devices_handler, users_handler])
    #Start bot
    app.run_polling()
