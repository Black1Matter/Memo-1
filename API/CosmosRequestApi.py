import requests, logging, toml, json
from logging.handlers import RotatingFileHandler
from WorkJson import WorkWithJson

config_toml = toml.load('config.toml')
work_json = WorkWithJson('settings.json')

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler2 = RotatingFileHandler(f"logs/CosmosRequest/{__name__}.log",maxBytes=config_toml['logging']['max_log_size'] * 1024 * 1024, backupCount=config_toml['logging']['backup_count'])
formatter2 = logging.Formatter("%(name)s %(asctime)s %(levelname)s %(message)s")
handler2.setFormatter(formatter2)
log.addHandler(handler2)

class CosmosRequestApi():
    CACHE_HEIGHT = dict()
    
    def __init__(self, rest: str, rpc: str, valoper_address: str) -> None:
        self.rest = rest
        self.rpc = rpc
        self.valoper_address = valoper_address
        self.tx_hash = []
        self.tx_hash_user = []
        self.executedAt = []


    def Get_address(
            self, 
            transaction_type: str
        ) -> list:
        log.info("#--Get_address--#")
        addresses = []
        
        if transaction_type == "DELEGATE": 
            answer = requests.get(f"{self.rest}/cosmos/staking/v1beta1/validators/{self.valoper_address}/delegations")
        
        elif transaction_type == "UNDELEGATE":
            answer = requests.get(f"{self.rest}/cosmos/staking/v1beta1/validators/{self.valoper_address}/unbonding_delegations")
        

        if answer.status_code == 200:
            log.info("Success, I get 200")
            log.debug(answer.text)
            data = json.loads(answer.text)
            for key in ['unbonding_responses', 'delegation_responses']:
                if data.get(key) != None and data.get(key) != []:
                    if key == "delegation_responses":
                        addresses = [item["delegation"]["delegator_address"] for item in data[key]]
                    elif key == "unbonding_responses":
                        addresses = [item["delegation"]["delegator_address"] for item in data[key]]

            return addresses

        
        else:
            log.error(f"Fail, I get {answer.status_code}")
            log.error(f"Answer with server: {answer.text}")

    def Get_Account_Wallet(
            self, 
            address: str
        ) -> int:
        log.info("#--Get_Account_Wallet--#")
        
        answer = requests.get(f"{self.rest}/cosmos/auth/v1beta1/accounts/{address}")

        if answer.status_code == 200:
            log.info("Success, I get 200")
            log.debug(answer.text)
            data = json.loads(answer.text)
            return int(data['account']['sequence']) - 1

        else:
            log.error(f"Fail, I get {answer.status_code}")
            log.error(f"Answer with server: {answer.text}")

    def Tx_Search(
            self,
            address: str,
            index_blocks: int = 10
        ) -> list:
        
        tx_hash = list()
        sequence = self.Get_Account_Wallet(address=address)
        tmp = 0

        while 0 < index_blocks - tmp:

            answer = requests.get(f"{self.rpc}/tx_search?query=\"tx.acc_seq='{address}/{sequence - tmp }'\"")
            if answer.status_code == 200:
                log.info("Success, I get 200")
                log.debug(answer.text)
                data = json.loads(answer.text)
                if data['tx']['body']['messages'][0] != []:
                    tx_hash.append(data['result']['txs'][0]['hash'])
                if sequence - tmp == 0:
                    break

                tmp += 1
                
            else:
                log.error(f"Fail, I get {answer.status_code}")
                log.error(f"Answer with server: {answer.text}")

        return tx_hash
        

    def Check_memo(
            self,
            address: str
    ) -> list:
        
        for tx_hash in self.Tx_Search(address=address):
            answer = requests.get(f"{self.rest}/cosmos/tx/v1beta1/txs/{tx_hash}")
            if answer.status_code == 200:
                log.info("Success, I get 200")
                log.debug(answer.text)
                data = json.loads(answer.text)
                if data['result']['txs'] != []:
                    tx_hash.append(data['result']['txs'][0]['hash'])

                
            else:
                log.error(f"Fail, I get {answer.status_code}")
                log.error(f"Answer with server: {answer.text}")

    
    def Get_Memo_Address_With_Transaction(
            self,
            hash: str
    ) -> dict:
        answer = requests.get(f"{self.rest}/cosmos/tx/v1beta1/txs/{hash}")

        if answer.status_code == 200:
            log.info("Success, I get 200")
            log.debug(answer.text)
            data = json.loads(answer.text)
            # type_transactions = data['messages'][0]['@type']

            # if data['messages'][0]['@type'][-8:].upper() 
            return data['tx']['body']
        
        else:
            log.error(f"Fail, I get {answer.status_code}")
            log.error(f"Answer with server: {answer.text}")
        

    def Get_Hash_Transactions_Height(
            self,
            height: int
    ) -> list:
        
        answer = requests.get(f"{self.rpc}/tx_search?query=\"tx.height={height}\"")

        if answer.status_code == 200:
            log.info("Success, I get 200")
            log.debug(answer.text)
            data = json.loads(answer.text)
            return [tmp['hash'] for tmp in data['result']['txs']]
        
        else:
            log.error(f"Fail, I get {answer.status_code}")
            log.error(f"Answer with server: {answer.text}")

    def Get_Memo(
            self,
            height: int,
            transactions_types: dict,
            wallet_types: dict
    ) -> dict:
        
        cache_hashes = {}

        for hash in self.Get_Hash_Transactions_Height(height=height):
            
            
            data = self.Get_Memo_Address_With_Transaction(hash=hash)

            for transactions_type in transactions_types:
                if data['messages'][0]['@type'][-len(transactions_type.get('name')):].upper() != transactions_type.get('name') or \
                    data['validator_address'] != self.valoper_address:
                    continue
                
                for wallet_type in wallet_types:
                    
                    if data['memo'] != wallet_type.get('name'):
                        continue
                # if data['memo'] not in wallet_types:
                #     continue

                # if data['validator_address'] != self.valoper_address:
                #     continue

                    
                    amount = int(data['messages']['amount']['amount']) / 1000000
                    time = data['tx_response']['timestamp']

                    if data["memo"] == wallet_type.get('name'):
                        cache_hashes[data['delegator_address']] = {'memo': wallet_type.get('id'), 
                                                                   'typeId': transactions_type.get('id'), 
                                                                   'amount': amount,
                                                                   'hash': hash,
                                                                   'time': time
                                                                   }

        return cache_hashes

    

    def get_height(self) -> int:

        answer = requests.get(f"{self.rpc}/status")
        if answer.status_code == 200:
            log.info("Success, I get 200")
            log.debug(answer.text)
            data = json.loads(answer.text)
            return int(data['result']['sync_info']['latest_block_height'])

        else:
            log.error(f"Fail, I get {answer.status_code}")
            log.error(f"Answer with server: {answer.text}")


    def Check_Block_Memo(
            self,
            transactions_type: dict,
            wallet_type: dict
    ) -> dict:
        try:
            settings_json = work_json.get_json()
            height = settings_json['last_height']
            last_height_network = self.get_height()
            cache_hashes = {}
            
            
            
            if height == None:
                height = last_height_network

            for tmp_height in range(height, last_height_network):
                
                log.info(f"\n\nHeight: {tmp_height} - {last_height_network}\n")
                memo = self.Get_Memo(tmp_height, transactions_types=transactions_type, wallet_types=wallet_type)
                if memo != {}:
                    cache_hashes[tmp_height] = memo

            settings_json['last_height'] = last_height_network
            work_json.set_json(settings_json)
            return cache_hashes
        except:
            log.exception("Error Cosmos API")
            return {}

        

# a = CosmosRequestApi(config_toml["network"]["Cosmos"]["rest"], config_toml["network"]["Cosmos"]["rpc"], config_toml["network"]["Cosmos"]["valoper_address"])
# a.Get_address()
# a.Check_memo("cosmos1rf045g5uj00zkwt24hjlcrw89htjzxuuq8t6gm")
# m = a.Check_Block_Memo(['DELEGATE', 'UNDELEGATE'], ['trast', 'ufir'])
# print(m)