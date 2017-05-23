from __future__ import print_function
import unittest
from pooledbismuth.pool import ConsensusBlock, ResultsManager


testdata_1 = [
    ConsensusBlock(height=105939, hash='094c61c63e3ba6c124cdbf642d45bc19784034c278f8ee9765404188', stamp=1495404043.8),
    ConsensusBlock(height=105940, hash='1635fac94e4f76d2b95a62b895a71748b8442b24e43b37e03630027a', stamp=1495404063.62),
    ConsensusBlock(height=105941, hash='def1383def27248de80e3c945274f4d507118fb53dd9af1f1228b7f1', stamp=1495404067.49),
    ConsensusBlock(height=105942, hash='c01ee850612e1c6dc623d6b651aba07e2c7d10b24130fe861eaaed1f', stamp=1495404082.81),
    ConsensusBlock(height=105943, hash='0b7c4edde83d5a4ad18bcebdeac580d0008943c7bb0ba2acdacbf400', stamp=1495404104.46),
    ConsensusBlock(height=105944, hash='b9a2b501c6e504bacc8997b10ec56d2a93085b899b0ae57b524213ff', stamp=1495404115.28),
    ConsensusBlock(height=105945, hash='47df91d9d09fb933061bd99fd610686d8e11c23d73e769a84e87b266', stamp=1495404149.0),
    ConsensusBlock(height=105946, hash='d4eb5059565ffe3af12d6aa266034392bfe765e99e99e238e1eb7633', stamp=1495404152.12),
    ConsensusBlock(height=105947, hash='ec4d854fa373d0854d3c62f53e9bde6cd982ac79bb0f9a592b775c50', stamp=1495404176.77),
    ConsensusBlock(height=105948, hash='94136a6c82d730b5af3f9ace12a51bf360519673c02f14fa5724d70c', stamp=1495404216.75),
    ConsensusBlock(height=105949, hash='0716deb7f3f5e038b0ff68780d0eb2e978f08d6adc0fc5f63333a857', stamp=1495404255.51),
    ConsensusBlock(height=105950, hash='89299c882eb3d10a13b130245448caff64e622a8a56ae6d6b3d1731f', stamp=1495404387.86),
    ConsensusBlock(height=105951, hash='a26868a44d48ed563d0d611142c5c2d6776ba1314f68a8bdf18db2cc', stamp=1495404502.22),
    ConsensusBlock(height=105952, hash='95ffea07fcc2dc23b9fe4e273bf14627522391669ed3824b474a66d3', stamp=1495404755.34),
    ConsensusBlock(height=105953, hash='0ef9e43bf34c2d6251dac2f4161b5c1da5b66c676aa55ef5f95803cd', stamp=1495404908.56),
    ConsensusBlock(height=105954, hash='a2c841c2b423bff586e19a0a7e379670a4545d3ead8ef6412c812706', stamp=1495404920.65),
    ConsensusBlock(height=105955, hash='9ab5f56bd3498a1985932f2d6d88d6ac89df7617753f6ce894230f4a', stamp=1495404949.66),
    ConsensusBlock(height=105956, hash='d65d16a7081bd5db572d8f63536003c4dc7ad6f673660a220bf9da31', stamp=1495404964.42),
    ConsensusBlock(height=105957, hash='0344325ede9be4e1a0871b37539448e0d87b258450662613b493463e', stamp=1495405011.07),
    ConsensusBlock(height=105958, hash='e2ab2704e43207d64bee94ca1a5de237ff313693d7df23ffe9783392', stamp=1495405237.12),
    ConsensusBlock(height=105959, hash='0f522f0601f167878bdc3525b5fba17ad327329ca5b6a5a93e11fe97', stamp=1495405265.98),
    ConsensusBlock(height=105960, hash='4e51d4f0fc2667ebcec39b33d7062f06f3cce3866fbc10cb291e3f4f', stamp=1495405290.74),
    ConsensusBlock(height=105961, hash='0caee70a5afbd7317a9a3a07e01d96360ae8e399779ddbb99667107a', stamp=1495405306.04),
    ConsensusBlock(height=105962, hash='b58eab0c6b890a79251c780f0a47e55510b85dc45418fe795f023489', stamp=1495405332.71),
    ConsensusBlock(height=105963, hash='2283c1549ae96ac3952248e742a2032825a6194248100c087c92e4aa', stamp=1495405334.74),
    ConsensusBlock(height=105964, hash='d0fd8861c3a3cc414456ea9629184ae6aa96232beae651a4989e701d', stamp=1495405376.67),
    ConsensusBlock(height=105965, hash='88f70f59bd6e816b1544eb6309e0c5e09b8c06db7dde68394968dc12', stamp=1495405499.31),
    ConsensusBlock(height=105966, hash='cbe1b9c47d00b8e2b89c98f4f62a32a67b8780f2490f60703dab50b5', stamp=1495405578.82),
    ConsensusBlock(height=105967, hash='5c0206bd87b1c4280da30cd9e010a65d07e89a1658de0052ed69a39a', stamp=1495405887.97),
    ConsensusBlock(height=105968, hash='8c6bb83b247fa26df571b408c221a71146ef79eca94c02fb1b8ea611', stamp=1495405947.87),
    ConsensusBlock(height=105969, hash='6998cd6a16c298c35e0b6e083e707acc5d215e9e7f87d9a29b16993a', stamp=1495405968.06),
    ConsensusBlock(height=105970, hash='be9066ea0e98c23337457e2dfbb99c860388040b159ac67938784af6', stamp=1495405970.09),
    ConsensusBlock(height=105971, hash='b8f2dc0c6254ebf6f16abba295bdc32f6c4f6348de35316dceff75ad', stamp=1495405972.03),
    ConsensusBlock(height=105972, hash='e5efcfc2b2ca26db3cd50fa0e93035e8091502f0f8e3564d4888da2e', stamp=1495405973.9),
    ConsensusBlock(height=105973, hash='46df3de14c9dc14c7d9ce9c6fddce97e8025583aa8a0f52f49406eab', stamp=1495405975.76),
    ConsensusBlock(height=105974, hash='eb408d53127222bf69470caca490f846fbfeed00653f906bda44ce5e', stamp=1495405977.7),
    ConsensusBlock(height=105975, hash='ebdcc5c48c086637694407a2c62eee50b3748e6129a61bc567ccd97f', stamp=1495405980.69),
    ConsensusBlock(height=105976, hash='10fd1dabd27474557cacb72aa83b1d30a48ac906f5e74257c8a4f054', stamp=1495405982.85),
    ConsensusBlock(height=105977, hash='9ad4cfad057cf747ac991376ce9573afbcb00bafae9bfc9e7e5cf185', stamp=1495405989.97),
    ConsensusBlock(height=105978, hash='58dfcbddfef07cea3e6e2802ac5033e47caf2cf1566808a696823179', stamp=1495405992.04),
    ConsensusBlock(height=105979, hash='fbf1423dd76ef2e881b7c6077d5de54a59f978fa7e48aca16b002b8c', stamp=1495406005.3),
    ConsensusBlock(height=105980, hash='865bb636945908abe24c7074518da9ab7c376bf3f98b36cbe7ef07e5', stamp=1495406062.72),
    ConsensusBlock(height=105981, hash='aa586d152789d99c65a83664eac536c1957db0d257444e397b4db5b6', stamp=1495406185.26),
    ConsensusBlock(height=105982, hash='d8b62e708a9df54e834b2a9e43a4db847cd8b41277b21024a4416aa0', stamp=1495406223.23),
    ConsensusBlock(height=105983, hash='4e07f478f34d80cc0d8315308c709e5dce99efa414234022af9da3ff', stamp=1495406261.03),
    ConsensusBlock(height=105984, hash='57fd88dbb24afd38d171ade221155dc0ddbfc9a7d64e75fe25e55e60', stamp=1495406562.42),
    ConsensusBlock(height=105985, hash='fccf08a75d52d7f8b85fe1fab5c3df9835cb57a493caf7c6162f7e6c', stamp=1495406623.48),
    ConsensusBlock(height=105986, hash='cf07d1c352730cf47468e36b71841f5072d38ff8981ae1668923fb69', stamp=1495406752.27),
    ConsensusBlock(height=105987, hash='21e560ab9315c6b2726a6a6390d365df5f0adc4d1be5ad13447a1131', stamp=1495406754.52),
]


class TestHistory(unittest.TestCase):
    def test_foo(self):
        testdata_2 = [
            ConsensusBlock(height=105939, hash='094c61c63e3ba6c124cdbf642d45bc19784034c278f8ee9765404188', stamp=1495404043.8),
            ConsensusBlock(height=105940, hash='1635fac94e4f76d2b95a62b895a71748b8442b24e43b37e03630027a', stamp=1495404063.62),
            ConsensusBlock(height=105941, hash='def1383def27248de80e3c945274f4d507118fb53dd9af1f1228b7f1', stamp=1495404067.49),
            ConsensusBlock(height=105942, hash='c01ee850612e1c6dc623d6b651aba07e2c7d10b24130fe861eaaed1f', stamp=1495404082.81),
            ConsensusBlock(height=105943, hash='0b7c4edde83d5a4ad18bcebdeac580d0008943c7bb0ba2acdacbf400', stamp=1495404104.46),
            ConsensusBlock(height=105942, hash='c01ee850612e1c6dc623d6b651aba07e2c7d10b24130fe861eaaed1f', stamp=1495404082.81),
            ConsensusBlock(height=105943, hash='0b7c4edde83d5a4ad18bcebdeac580d0008943c7bb0ba2acdacbf400', stamp=1495404104.46),
            ConsensusBlock(height=105944, hash='b9a2b501c6e504bacc8997b10ec56d2a93085b899b0ae57b524213ff', stamp=1495404115.28),
            ConsensusBlock(height=105944, hash='0b7c4edde83d5a4ad18bcebdeac580d0008943c7bb0ba2acdacbf400', stamp=1495404115.28),
        ]
        ResultsManager.reset()
        for row in testdata_2:
            ResultsManager.on_consensus(row, row.stamp)
        assert ResultsManager.HISTORY[-1].height == 105944


if __name__ == '__main__':
    unittest.main()
