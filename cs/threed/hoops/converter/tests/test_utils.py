import os
import unittest

from cdb.objects.pdd import Sandbox

from cs.threed.hoops.converter import utils


class TestConverterUtils(unittest.TestCase):
    def setUp(self):
        super(TestConverterUtils, self).setUp()

        self.xml_filename = "root_doc.xml"
        self.xml_content = '''
            <Root>
                <ModelFile>
                    <ProductOccurence Id="0" Name="Root" ExchangeId="" Children="1"/>
                    <ProductOccurence Id="1" Name="Root" ExchangeId="Root.d870e1dea4ce9da3cd2029ce868f604da02848" FilePath="./root_doc.CATProduct" Children="2 3" IsPart="false">
                    <Transformation RelativeTransfo="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>
                    </ProductOccurence>
                    <ProductOccurence Id="2" Name="Child1" ExchangeId="Child1.d870e1dea4ce9da3cd2029ce868f604da02830" FilePath="./child_1.CATPart">
                    <Transformation RelativeTransfo="2 0 0 0 0 2 0 0 0 0 2 0 0 0 0 2"/>
                    </ProductOccurence>
                    <ProductOccurence Id="5" Name="" ExchangeId="" FilePath="./child_1.CATPart">
                    <Transformation RelativeTransfo="3 0 0 0 0 3 0 0 0 0 3 0 0 0 0 3"/>
                    </ProductOccurence>
                    <ProductOccurence Id="3" Name="Child2" ExchangeId="Child2.d870e1dea4ce9da3cd2029ce868f604da02840" FilePath="./child_2.CATPart">
                    <Transformation RelativeTransfo="4 0 0 0 0 4 0 0 0 0 4 0 0 0 0 4"/>
                    </ProductOccurence>
                    <ProductOccurence Id="9" Name="" ExchangeId="" FilePath="./child_2.CATPart">
                    <Transformation RelativeTransfo="5 0 0 0 0 5 0 0 0 0 5 0 0 0 0 5"/>
                    </ProductOccurence>
                </ModelFile>
            </Root>
        '''

        self.json_exp_content = '{"default_config": "DEFAULT", "by_exchange_id": {"Root.d870e1dea4ce9da3cd2029ce868f604da02848": {"filename": "root_doc.CATProduct", "transform": "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1", "path": []}, "Child1.d870e1dea4ce9da3cd2029ce868f604da02830": {"filename": "child_1.CATPart", "transform": "2 0 0 0 0 2 0 0 0 0 2 0 0 0 0 2", "path": ["Child1.d870e1dea4ce9da3cd2029ce868f604da02830"]}, "Child2.d870e1dea4ce9da3cd2029ce868f604da02840": {"filename": "child_2.CATPart", "transform": "4 0 0 0 0 4 0 0 0 0 4 0 0 0 0 4", "path": ["Child2.d870e1dea4ce9da3cd2029ce868f604da02840"]}}, "by_filename": {"root_doc.CATProduct": ["Root.d870e1dea4ce9da3cd2029ce868f604da02848"], "child_1.CATPart": ["Child1.d870e1dea4ce9da3cd2029ce868f604da02830"], "child_2.CATPart": ["Child2.d870e1dea4ce9da3cd2029ce868f604da02840"]}, "by_filename_path": {"DEFAULT": {"children": {"root_doc.CATProduct": {"exchange_ids": ["Root.d870e1dea4ce9da3cd2029ce868f604da02848"], "children": {"child_1.CATPart": {"exchange_ids": ["Child1.d870e1dea4ce9da3cd2029ce868f604da02830"]}, "child_2.CATPart": {"exchange_ids": ["Child2.d870e1dea4ce9da3cd2029ce868f604da02840"]}}}}}}}'

    def test_create_json_from_xml(self):
        """a JSON file with the right content is created from the XML"""

        with Sandbox() as sb:
            xml_path = os.path.join(sb.location, self.xml_filename)

            with open(xml_path, "w") as f:
                f.write(self.xml_content)
                f.close()

            json_path = utils.convert_xml_to_json(xml_path)

            self.assertTrue(os.path.exists(json_path), "json file should exist")

            with open(json_path) as f:
                self.assertTrue(f.read() == self.json_exp_content, "wrong output in json")
                f.close()
