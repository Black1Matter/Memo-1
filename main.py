import logging, toml, time, asyncio
from datetime import datetime

from logging.handlers import RotatingFileHandler
from function import * 
from API import MemeApi, CosmosRequestApi
from WorkJson import WorkWithJson


config_toml = toml.load('config.toml')
work_json = WorkWithJson('settings.json')


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

log_s = logging.StreamHandler()
log_s.setLevel(logging.INFO)
formatter2 = logging.Formatter("%(name)s %(asctime)s %(levelname)s %(message)s")
log_s.setFormatter(formatter2)

log_f = RotatingFileHandler(f"logs/{__name__}.log",maxBytes=config_toml['logging']['max_log_size'] * 1024 * 1024, backupCount=config_toml['logging']['backup_count'])
log_f.setLevel(logging.DEBUG)
formatter2 = logging.Formatter("%(name)s %(asctime)s %(levelname)s %(message)s")
log_f.setFormatter(formatter2)

log.addHandler(log_s)
log.addHandler(log_f)




cache_users = None
user_delegates = None

async def process_network(name_network: dict, data: dict):
    id_log = data["id"]
    memo = MemeApi.MemeApi(id=id_log, network=name_network.get('name'))

    try: 
        id_network = str(name_network.get('id'))
        cosmos = CosmosRequestApi.CosmosRequestApi(
            rest=config_toml['network'][name_network.get('name')]['rest'],
            rpc=config_toml['network'][name_network.get('name')]['rpc'],
            valoper_address=config_toml['network'][name_network.get('name')]['valoper_address'],
            id=id_log,
            network=name_network.get("name")
        )
        # APR = update_APR(cosmos.Get_All_Rewards(config_toml['network'][name_network.get('name')]['address']))
        transactions_type = await memo.Get_Available_Transaction_Types()
        wallet_type = await memo.Get_Available_Wallet_Types()

       
        if id_network not in cache_users:
            cache_users[id_network] = {}

        if id_network not in user_delegates:
            user_delegates[id_network] = {}

        data_memo_address_time = await cosmos.Get_Block_Memo(transactions_type=transactions_type, wallet_type=wallet_type, address_user=cache_users[id_network], settings_json=data)

        for height in data_memo_address_time:
            for address in data_memo_address_time[height]:
                memo_id = str(data_memo_address_time[height][address]["memo"])
                if memo_id not in  cache_users[id_network]:
                    cache_users[id_network][memo_id] = {}
                
                if memo_id not in  cache_users[id_network]:
                    user_delegates[id_network][memo_id] = {}

                if address not in cache_users[id_network][memo_id]:
                    log.info(f"{id_log} | {name_network.get('name')}  ->  Add new user with: {address}")
                    userId = memo.Add_New_User(address=address, walletType=data_memo_address_time[height][address]['memo'], blockchain=name_network.get('id'))
                    cache_users[id_network][memo_id][address] = userId
                    user_delegates[id_network][memo_id][address] = 0

                if data_memo_address_time[height][address]['typeId'] == 1:
                    user_delegates[id_network][memo_id][address] += float(data_memo_address_time[height][address]['amount'])
                elif data_memo_address_time[height][address]['typeId'] == 2 and user_delegates[id_network][memo_id][address] >= float(data_memo_address_time[height][address]['amount']):
                    user_delegates[id_network][memo_id][address] -= float(data_memo_address_time[height][address]['amount'])
                else:
                    user_delegates[id_network][memo_id][address] = 0

                userId = cache_users[id_network][memo_id][address]
                memo.Add_New_Transactions(userId=userId, 
                                        typeId=data_memo_address_time[height][address]['typeId'],
                                        amount=data_memo_address_time[height][address]['amount'],
                                        executedAt=str(to_tmpstmp_mc(data_memo_address_time[height][address]['time'])),
                                        hash=data_memo_address_time[height][address]['hash']
                                        )
                
        # if data["last_completion_time"] == None:
        for memo_id in cache_users[id_network]:
            for address in cache_users[id_network][memo_id]:
                if user_delegates[id_network][memo_id][address] == 0:
                    continue
                
                amountReward_user, amountReward_Validator = get_APR_from(user_delegates[id_network][memo_id][address], data["APR"][name_network.get('name')])
                log.info(f"{id_log} | {name_network.get('name')}  ->  | Address {address}  | All rewards user: {amountReward_user} + commission {amountReward_Validator}  APR {data['APR'][name_network.get('name')]}")

                userId = cache_users[id_network][memo_id][address]
                memo.Update_User_Stats(userId, amountReward_user, amountReward_Validator)

    except:
        log.exception("ERROR Main")


async def main():
    global cache_users, user_delegates
    data = work_json.get_json()
    id_log = data["id"]
    memo = MemeApi.MemeApi(id=id_log, network="TYPE START")

    while True:
        log.info("Start")
        
        star_time = time.time()
        change_blockchain = []

        if cache_users == None:
            cache_users = memo.Get_Cache()
        
        if user_delegates == None:
            user_delegates = memo.Get_Users_Delegated_Amounts()

        for blockchain in memo.Get_Available_Blockchains_Types():
            if config_toml['network']['isMainnet'] == blockchain.get('isMainnet'):
                change_blockchain.append(blockchain)
        
        log.info(change_blockchain)
        

        tasks = [process_network(name_network, data) for name_network in change_blockchain]
        await asyncio.gather(*tasks)
        
        # data["last_completion_time"] = datetime.now()
        data["id"] += 1
        work_json.set_json(data=data)
        log.info(f"Time work: {time.time() - star_time:.4f}")
        log.info(f"wait {config_toml['time_update'] } min")
        time.sleep(config_toml['time_update'] * 60)
        




if __name__ == '__main__':
    asyncio.run(main())