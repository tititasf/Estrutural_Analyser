import json
import httpx
import pytest
from portal.app import auth
from portal.app.main import create_app
from portal.db import connection, repository as repo

@pytest.mark.asyncio
async def test_save_fields_changes_list_and_n3_access(settings,tmp_path):
    obra_dir=tmp_path/'obra';obra_dir.mkdir()
    original={'pilares':[{'name':'P1','classification':'NASCE','orientation':'RETANGULAR VERTICAL','points':[[0,0],[20,0],[20,60],[0,60]]}]}
    (obra_dir/'estado_13_PAV.json').write_text(json.dumps(original))
    c=connection.init_db(settings.db_path)
    m=repo.criar_membro(c,login='ana',nome='Ana',senha_hash=auth.hash_senha('test123'),drive_folder_id='a')
    member=repo.obter_membro_por_login(c,'ana')
    obra=repo.criar_obra(c,membro_id=member['id'],nome='Obra',pasta_drive_id='o',arquivo_hash='x',estado='pronta',local_path=str(obra_dir));c.close()
    app=create_app(settings)
    async with app.router.lifespan_context(app):
      async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        await client.post('/login',json={'login':'ana','senha':'test123'})
        url=f'/obras/{obra}/n1/pilares/P1'
        listing=await client.get(f'/obras/{obra}/n1/pilares?pavimento=13_PAV')
        assert listing.status_code==200,listing.text
        assert listing.json()['itens'][0]['classification']=='NASCE'
        assert (await client.get(url+'/pilar-n3-ficha?pavimento=13_PAV')).status_code==409
        assert (await client.post(url+'/pilar-n3-cima/regenerar?pavimento=13_PAV')).status_code==409
        assert not (await client.put(url+'/sa-review?pavimento=13_PAV',json={'fields':{'pe_direito':280}})).json()['n3_n5_eligible']
        fields={'classificacao':'SEGUE','orientacao':'RETANGULAR HORIZONTAL','nivel_saida':848.98,'nivel_chegada':852.19,'pe_direito':321}
        response=await client.put(url+'/sa-review?pavimento=13_PAV',json={'fields':fields})
        assert response.status_code==200,response.text
        assert response.json()['n3_n5_eligible']
        assert (await client.get(url+'/pilar-n3-ficha?pavimento=13_PAV')).status_code==200
        assert (await client.get(f'/obras/{obra}/n1/pilares?pavimento=13_PAV')).json()['itens'][0]['classification']=='SEGUE'
        assert (await client.put(url+'/sa-review?pavimento=13_PAV',json={'fields':{'pe_direito':-1}})).status_code==422
        assert json.loads((obra_dir/'estado_13_PAV.json').read_text())==original
