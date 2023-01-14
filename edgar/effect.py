from bs4 import BeautifulSoup
import pandas as pd
from edgar.core import repr_rich, df_to_rich_table
from rich.console import Group, Text
from functools import lru_cache
from edgar.xml import child_text
from typing import Optional
from edgar import get_company

__all__ = [
    'Filer',
    'EffectiveData',
    'Effect'
]


class Filer:

    def __init__(self,
                 cik: str,
                 entity_name: str,
                 file_number: str
                 ):
        self.cik: str = cik
        self.entity_name: str = entity_name
        self.file_number: str = file_number


class EffectiveData:
    """

    """

    def __init__(self,
                 final_effective_date: str,
                 file_number: str,
                 accession_no: Optional[str],
                 submission_type: Optional[str],
                 form: Optional[str],
                 filer: Filer
                 ):
        self.final_effective_date: str = final_effective_date
        self.file_number: Optional[str] = file_number
        self.accession_no: Optional[str] = accession_no
        self.form: Optional[str] = form
        self.submission_type: str = submission_type
        self.filer: Filer = filer


class Effect:
    """
    A edgar submission parsed from an EFFECT form xml
    """

    def __init__(self,
                 submission_type: str,
                 effectiveness_data: EffectiveData,
                 is_live: bool,
                 schema_version: str = None
                 ):
        self.submission_type = submission_type
        self.effectiveness_data = effectiveness_data
        self.is_live = is_live
        self.schema_version = schema_version

    @property
    def effective_date(self) -> str:
        return self.effectiveness_data.final_effective_date

    @property
    def cik(self):
        if self.effectiveness_data.filer:
            return self.effectiveness_data.filer.cik

    @property
    def entity(self):
        if self.effectiveness_data.filer:
            return self.effectiveness_data.filer.entity_name

    @property
    def source_submission_type(self):
        return self.effectiveness_data.submission_type or self.effectiveness_data.form or ""

    @property
    def source_accession_no(self):
        return self.effectiveness_data.accession_no

    @property
    def source_filing(self):
        if self.source_accession_no:
            """Search for the source filing using the accession number"""
            company = get_company(cik=self.cik)
            filings = company.get_filings(accession_number=self.source_accession_no)
            if len(filings) == 1:
                return filings[0]
        elif self.effectiveness_data.file_number and self.effectiveness_data.form:
            """Search for the source filing using the file number and form"""
            company = get_company(cik=self.cik)
            filings = company.get_filings(file_number=self.effectiveness_data.file_number,
                                          form=self.effectiveness_data.form)
            if len(filings) > 0:
                return filings[0]

    @lru_cache(maxsize=1)
    def summary(self) -> pd.DataFrame:
        return pd.DataFrame([{"live": self.is_live,
                              "entity": self.entity,
                              "cik": self.cik,
                              "effective": self.effective_date}]).set_index("effective")

    def __str__(self):
        return (f"EffectSubmission(effective='{self.effective_date}', type='{self.submission_type}', "
                f"is_live={self.is_live}, entity='{self.entity}')")

    def __rich__(self) -> str:
        return Group(Text(f"{self.submission_type} filing for form {self.source_submission_type} filing"),
                     df_to_rich_table(self.summary(), index_name="effective")
                     )

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def from_xml(cls,
                 submission_xml: str):
        """
        <edgarSubmission>
            <schemaVersion>X0101</schemaVersion>
            <submissionType>EFFECT</submissionType>
            <act>33</act>
            <testOrLive>LIVE</testOrLive>
            <effectiveData>
                <finalEffectivenessDispDate>2022-11-22</finalEffectivenessDispDate>
                <accessionNumber>0000038723-22-000117</accessionNumber>
                <submissionType>POS AM</submissionType>
                <filer>
                    <cik>0000038723</cik>
                    <entityName>1st FRANKLIN FINANCIAL CORP</entityName>
                    <fileNumber>333-237642</fileNumber>
                </filer>
            </effectiveData>
        </edgarSubmission>
        """
        soup = BeautifulSoup(submission_xml, "xml")
        root = soup.find("edgarSubmission")
        schema_version = root.find("schemaVersion").text
        test_or_live_el = root.find("testOrLive")
        is_live = test_or_live_el and test_or_live_el.text == 'LIVE'

        # Effective data
        effectiveness_el = root.find("effectiveData")
        effectiveness_el.find("finalEffectivenessDispDate")

        filer_el = effectiveness_el.find("filer")
        accession_no = child_text(effectiveness_el, "accessionNumber")
        file_number = child_text(effectiveness_el, "fileNumber")
        source_submission_type = child_text(effectiveness_el, "submissionType")
        source_form = child_text(effectiveness_el, "form")

        return cls(
            submission_type=root.find("submissionType").text,
            schema_version=schema_version,
            is_live=is_live,
            effectiveness_data=EffectiveData(
                final_effective_date=effectiveness_el.find("finalEffectivenessDispDate").text,
                accession_no=accession_no,
                file_number=file_number,
                submission_type=source_submission_type,
                form=source_form,
                filer=Filer(
                    cik=filer_el.find("cik").text,
                    entity_name=filer_el.find("entityName").text,
                    file_number=filer_el.find("fileNumber").text
                )
            )
        )
